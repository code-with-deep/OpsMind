"""Allowlisted, read-only SQL investigation tool."""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from opsmind.domain.evidence import Evidence
from opsmind.grounding.registry import SourceIdRegistry, default_registry
from opsmind.memory.persist import persist_tool_result
from opsmind.tools.sql_templates import (
    ALLOWLISTED_TABLES,
    FORBIDDEN_SQL_RE,
    SqlTemplate,
    get_template,
)

_READONLY_ENGINE: Engine | None = None
_READONLY_SESSION: sessionmaker[Session] | None = None


class SqlToolError(ValueError):
    """Controlled error for allowlist / parameter / safety violations."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row_to_dict(mapping: Any) -> dict[str, Any]:
    return {k: _jsonable(v) for k, v in dict(mapping).items()}


def _fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _assert_template_safe(template: SqlTemplate) -> None:
    sql_upper = template.sql.upper()
    if re.search(FORBIDDEN_SQL_RE, sql_upper, flags=re.IGNORECASE):
        raise SqlToolError(
            f"Template '{template.key}' contains a forbidden SQL verb; refusing to run"
        )
    if "SELECT" not in sql_upper:
        raise SqlToolError(f"Template '{template.key}' is not a SELECT query")
    for table in template.allowlisted_tables:
        if table not in ALLOWLISTED_TABLES:
            raise SqlToolError(
                f"Template '{template.key}' references non-allowlisted table '{table}'"
            )


def _validate_params(template: SqlTemplate, params: dict[str, Any]) -> dict[str, Any]:
    missing = [p for p in template.required_params if p not in params or params[p] in (None, "")]
    if missing:
        raise SqlToolError(
            f"Missing required params for '{template.key}': {', '.join(missing)}"
        )
    # Only bind declared params — ignore extras to avoid injection via unexpected binds.
    return {k: params[k] for k in template.required_params}


def get_readonly_engine(database_url_readonly: str) -> Engine:
    global _READONLY_ENGINE, _READONLY_SESSION
    if _READONLY_ENGINE is None:
        # asyncpg URLs are for the API; tools use sync psycopg2.
        url = database_url_readonly.replace("postgresql+asyncpg://", "postgresql://")
        _READONLY_ENGINE = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=5)
        _READONLY_SESSION = sessionmaker(_READONLY_ENGINE, expire_on_commit=False)
    return _READONLY_ENGINE


def get_readonly_session_factory(database_url_readonly: str) -> sessionmaker[Session]:
    get_readonly_engine(database_url_readonly)
    assert _READONLY_SESSION is not None
    return _READONLY_SESSION


def dispose_readonly_engine() -> None:
    global _READONLY_ENGINE, _READONLY_SESSION
    if _READONLY_ENGINE is not None:
        _READONLY_ENGINE.dispose()
        _READONLY_ENGINE = None
        _READONLY_SESSION = None


@dataclass
class SqlToolResult:
    evidence: Evidence
    rows: list[dict[str, Any]]
    template_key: str
    source_id: str
    latency_ms: int
    tool_invocation_id: str | None
    finding_id: str | None


def run_sql_tool(
    *,
    template_key: str,
    params: dict[str, Any],
    database_url_readonly: str,
    owner_session: Session,
    investigation_id: uuid.UUID | None = None,
    registry: SourceIdRegistry | None = None,
    persist: bool = True,
) -> SqlToolResult:
    """Execute an allowlisted SQL template via the read-only role and persist evidence."""
    try:
        template = get_template(template_key)
    except KeyError as exc:
        raise SqlToolError(str(exc)) from exc

    _assert_template_safe(template)
    bind_params = _validate_params(template, params)

    started = time.perf_counter()
    factory = get_readonly_session_factory(database_url_readonly)
    with factory() as ro_session:
        result = ro_session.execute(text(template.sql), bind_params)
        rows = [_row_to_dict(row) for row in result.mappings().all()]
    latency_ms = int((time.perf_counter() - started) * 1000)

    source_id = f"sql_{template.key}_{uuid.uuid4().hex[:12]}"
    fp = _fingerprint(rows)

    if rows:
        claim = (
            f"SQL template '{template.key}' returned {len(rows)} row(s) "
            f"for params {bind_params}."
        )
        confidence = 0.9
        gaps: list[str] = []
    else:
        claim = (
            f"SQL template '{template.key}' returned no rows for params {bind_params}."
        )
        confidence = 0.4
        gaps = ["No matching rows in the selected window/filters."]

    evidence = Evidence(
        claim=claim,
        confidence=confidence,
        sources=[
            {
                "type": "sql_template",
                "template_key": template.key,
                "params": bind_params,
                "row_count": len(rows),
                "result_fingerprint": fp,
            }
        ],
        assumptions=["Business tables are seeded and up to date."],
        gaps=gaps,
        source_id=source_id,
    )

    reg = registry or default_registry
    reg.register(
        source_id,
        kind="sql",
        ref={
            "template_key": template.key,
            "params": bind_params,
            "row_count": len(rows),
            "fingerprint": fp,
        },
    )

    invocation_id: str | None = None
    finding_id: str | None = None
    if persist:
        inv, finding = persist_tool_result(
            owner_session,
            investigation_id=investigation_id,
            tool_name="sql",
            template_key=template.key,
            request={"params": bind_params},
            response_meta={"row_sample": rows[:5]},
            result_fingerprint=fp,
            row_count=len(rows),
            latency_ms=latency_ms,
            source_id=source_id,
            evidence=evidence,
        )
        invocation_id = str(inv.id)
        finding_id = str(finding.id)

    return SqlToolResult(
        evidence=evidence,
        rows=rows,
        template_key=template.key,
        source_id=source_id,
        latency_ms=latency_ms,
        tool_invocation_id=invocation_id,
        finding_id=finding_id,
    )
