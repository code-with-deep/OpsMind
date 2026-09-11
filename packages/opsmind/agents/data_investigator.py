"""Data Investigator agent — run allowlisted SQL tools from the plan."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import write_event
from opsmind.graph.state import InvestigationState
from opsmind.guardrails.budget import BudgetExceededError, consume_tool_budget
from opsmind.tools.sql_tool import SqlToolError, run_sql_tool

logger = logging.getLogger(__name__)


def data_investigator_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    plan = state.get("plan") or {}
    inv_id = uuid.UUID(state["investigation_id"])
    sql_steps = plan.get("sql_steps") or []
    retry_count = int(state.get("retry_count") or 0)
    blocked = set(runtime.get("blocked_templates") or [])
    # P2-12: test-only fixture (see test_p4_self_correction.py) that forces a
    # Critic retry by hiding SQL evidence on the first pass. Not reachable from
    # any API route — `run_investigation(runtime_overrides=...)` is only ever
    # called with this key set from tests/evals, never from request bodies
    # (create_and_run_investigation / investigations_create do not accept or
    # forward a runtime_overrides field from the client).
    if runtime.get("block_sql_on_first_pass") and retry_count == 0:
        blocked = blocked | {
            step.get("template_key")
            for step in sql_steps
            if step.get("template_key")
        }

    findings: list[dict[str, Any]] = []
    errors: list[str] = []

    factory = get_owner_session_factory(runtime["database_url_sync"])
    tenant_id = tenant_id_from_runtime(runtime)
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_data_investigator",
            payload={"sql_steps": len(sql_steps), "blocked": sorted(blocked)},
        )
        for step in sql_steps:
            key = step.get("template_key")
            params = step.get("params") or {}
            if key in blocked:
                errors.append(f"sql:{key}: blocked by fixture/policy")
                continue
            try:
                consume_tool_budget(runtime)
                result = run_sql_tool(
                    template_key=key,
                    params=params,
                    database_url_readonly=runtime["database_url_readonly"],
                    owner_session=session,
                    tenant_id=tenant_id,
                    investigation_id=inv_id,
                )
                findings.append(
                    {
                        "agent": "data_investigator",
                        "kind": "sql",
                        "purpose": step.get("purpose"),
                        "evidence": result.evidence.model_dump(),
                        "rows": result.rows[:50],
                        "source_id": result.source_id,
                    }
                )
            except BudgetExceededError as exc:
                errors.append(str(exc))
                break
            except SqlToolError as exc:
                # Author-controlled, safe to surface (allowlist/param violations etc).
                errors.append(f"sql:{key}: {exc}")
            except Exception as exc:  # noqa: BLE001
                # P1-13: raw DB/driver exceptions can contain table/column/constraint
                # names or parameter values — log full detail, surface only a generic
                # message in the persisted/returned errors list.
                logger.warning(
                    "sql_tool_unexpected_error investigation_id=%s template=%s error=%s",
                    inv_id, key, exc,
                )
                errors.append(f"sql:{key}: internal error while executing this query")

        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_data_investigator_done",
            payload={"findings": len(findings), "errors": errors},
        )

    out: dict[str, Any] = {
        "findings": findings,
        "node_trace": ["data_investigator"],
    }
    if errors:
        out["errors"] = errors
    return out
