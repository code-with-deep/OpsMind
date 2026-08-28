"""P2 tool demo routes — SQL, RAG, and date normalizer without an agent graph."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.app.auth import require_api_key
from api.app.config import get_settings
from opsmind.guardrails.input import check_input_guardrails
from opsmind.guardrails.output import sanitize_output_payload
from opsmind.memory.persist import create_investigation
from opsmind.tools.dates import normalize_date_range
from opsmind.tools.rag_tool import RagToolError, run_rag_tool
from opsmind.tools.sql_templates import list_templates
from opsmind.tools.sql_tool import SqlToolError, dispose_readonly_engine, run_sql_tool

router = APIRouter(
    prefix="/tools",
    tags=["tools"],
    dependencies=[Depends(require_api_key)],
)

_owner_engine = None
_owner_session_factory: sessionmaker[Session] | None = None


def get_owner_session() -> Iterator[Session]:
    global _owner_engine, _owner_session_factory
    settings = get_settings()
    if _owner_session_factory is None:
        _owner_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
        _owner_session_factory = sessionmaker(_owner_engine, expire_on_commit=False)
    session = _owner_session_factory()
    try:
        yield session
    finally:
        session.close()


class DateNormalizeRequest(BaseModel):
    expression: str
    as_of: date | None = None


class SqlRunRequest(BaseModel):
    template_key: str
    params: dict[str, Any] = Field(default_factory=dict)
    investigation_id: uuid.UUID | None = None


class RagRunRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.05
    investigation_id: uuid.UUID | None = None


class CreateInvestigationRequest(BaseModel):
    question: str
    window_start: date | None = None
    window_end: date | None = None


@router.get("/sql/templates")
def sql_templates() -> dict[str, Any]:
    return sanitize_output_payload({"templates": list_templates()})


@router.post("/dates/normalize")
def dates_normalize(body: DateNormalizeRequest) -> dict[str, Any]:
    try:
        rng = normalize_date_range(body.expression, as_of=body.as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return rng.as_dict()


@router.post("/investigations")
def investigations_create(
    body: CreateInvestigationRequest,
    session: Session = Depends(get_owner_session),
) -> dict[str, Any]:
    guard = check_input_guardrails(body.question)
    if not guard.allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "input_guardrail_rejected",
                "reason": guard.reason,
            },
        )
    inv = create_investigation(
        session,
        question=body.question,
        window_start=body.window_start,
        window_end=body.window_end,
    )
    return sanitize_output_payload(
        {
            "id": str(inv.id),
            "question": inv.question,
            "status": inv.status,
            "window_start": inv.window_start.isoformat() if inv.window_start else None,
            "window_end": inv.window_end.isoformat() if inv.window_end else None,
        }
    )


@router.post("/sql/run")
def sql_run(
    body: SqlRunRequest,
    session: Session = Depends(get_owner_session),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        result = run_sql_tool(
            template_key=body.template_key,
            params=body.params,
            database_url_readonly=settings.database_url_readonly,
            owner_session=session,
            investigation_id=body.investigation_id,
        )
    except SqlToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface DB/role issues clearly in demo
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return sanitize_output_payload(
        {
            "template_key": result.template_key,
            "source_id": result.source_id,
            "latency_ms": result.latency_ms,
            "tool_invocation_id": result.tool_invocation_id,
            "finding_id": result.finding_id,
            "row_count": len(result.rows),
            "rows": result.rows,
            "evidence": result.evidence.model_dump(),
        }
    )


@router.post("/rag/query")
def rag_query(
    body: RagRunRequest,
    session: Session = Depends(get_owner_session),
) -> dict[str, Any]:
    guard = check_input_guardrails(body.query)
    if not guard.allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "input_guardrail_rejected",
                "reason": guard.reason,
            },
        )
    try:
        result = run_rag_tool(
            query=body.query,
            owner_session=session,
            investigation_id=body.investigation_id,
            top_k=body.top_k,
            min_score=body.min_score,
        )
    except RagToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return sanitize_output_payload(
        {
            "source_id": result.source_id,
            "latency_ms": result.latency_ms,
            "tool_invocation_id": result.tool_invocation_id,
            "finding_id": result.finding_id,
            "hits": [
                {
                    "doc_id": h.doc_id,
                    "doc_key": h.doc_key,
                    "title": h.title,
                    "chunk_index": h.chunk_index,
                    "score": h.score,
                    "content": h.content,
                }
                for h in result.hits
            ],
            "evidence": result.evidence.model_dump(),
        }
    )


def dispose_tool_engines() -> None:
    global _owner_engine, _owner_session_factory
    dispose_readonly_engine()
    if _owner_engine is not None:
        _owner_engine.dispose()
        _owner_engine = None
        _owner_session_factory = None
