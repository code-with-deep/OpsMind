"""Investigation API — LangGraph runs, reviews, and case memory (P6)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.auth import require_tenant_context, require_user_session
from api.app.config import get_settings
from api.app.deps import get_tenant_session
from api.app.errors import safe_internal_error
from opsmind.db.ingest_csv import tenant_data_ready
from opsmind.db.memory_models import Investigation
from opsmind.db.session import dispose_owner_engine, get_owner_session_factory
from opsmind.db.tenant_models import TenantSettings
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.domain.tenant import TenantContext
from opsmind.graph.runner import (
    list_investigations_view,
    load_investigation_view,
    reset_graph_cache,
    run_investigation,
)
from opsmind.guardrails.output import sanitize_output_payload
from opsmind.memory.persist import list_case_summaries, record_review

router = APIRouter(
    prefix="/investigations",
    tags=["investigations"],
    dependencies=[Depends(require_tenant_context)],
)


class CreateInvestigationBody(BaseModel):
    question: str = Field(min_length=3)
    wait: bool = Field(
        default=True,
        description="If true, run the graph to completion before responding.",
    )


class SubmitReviewBody(BaseModel):
    decision: Literal["approved", "rejected", "comment"] = Field(
        description="Operator decision for this investigation report."
    )
    # P1-8: `reviewer` is no longer client-supplied — it is taken from the
    # authenticated session (tenant.user_email) so a user cannot approve/reject
    # under someone else's identity, and API-key-only callers (no user identity)
    # cannot review at all.
    notes: str | None = Field(
        default=None,
        description="Optional feedback or rationale.",
    )


@router.get("")
def list_investigations(
    tenant: TenantContext = Depends(require_tenant_context),
    status: str | None = Query(None, description="Filter by terminal status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """List past investigations with status and approval markers (P6)."""
    items = list_investigations_view(
        session, tenant_id=tenant.tenant_id, limit=limit, offset=offset, status=status
    )
    return {
        "investigations": items,
        "count": len(items),
        "limit": limit,
        "offset": offset,
    }


@router.get("/cases/memory")
def get_case_memory(
    tenant: TenantContext = Depends(require_tenant_context),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """List approved case summaries in organizational memory (P6)."""
    cases = list_case_summaries(
        session, tenant_id=tenant.tenant_id, limit=limit, offset=offset
    )
    return {
        "cases": sanitize_output_payload(cases),
        "count": len(cases),
    }


@router.post("")
def create_and_run_investigation(
    body: CreateInvestigationBody,
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    settings = get_settings()
    if not body.wait:
        raise HTTPException(
            status_code=400,
            detail="Async enqueue is not enabled; set wait=true.",
        )

    ready = tenant_data_ready(session, tenant.tenant_id)
    if not ready["ready"]:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "tenant_data_not_ready",
                "reason": (
                    "Upload company CSV data in Settings before running investigations. "
                    "Required: products.csv, orders.csv, order_items.csv (ZIP)."
                ),
                "ready": ready,
            },
        )

    # P1-12: enforce the per-tenant daily investigation cap (soft_limits.max_investigations_per_day
    # is written at signup but was never read before this fix — each run costs SQL + LLM calls
    # against a metered API with no other throttle in front of it).
    tenant_settings_row = session.get(TenantSettings, tenant.tenant_id)
    soft_limits = dict((tenant_settings_row.soft_limits or {}) if tenant_settings_row else {})
    max_per_day = int(soft_limits.get("max_investigations_per_day") or 50)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    todays_count = session.scalar(
        select(func.count())
        .select_from(Investigation)
        .where(
            Investigation.tenant_id == tenant.tenant_id,
            Investigation.created_at >= day_ago,
        )
    ) or 0
    if int(todays_count) >= max_per_day:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_investigation_limit_reached",
                "reason": f"Daily limit of {max_per_day} investigations reached for this workspace.",
                "limit": max_per_day,
            },
        )

    try:
        result = run_investigation(
            question=body.question,
            settings=settings,
            tenant_id=tenant.tenant_id,
            user_id=tenant.user_id,
        )
    except Exception as exc:  # noqa: BLE001
        # P1-13: never leak raw exception text (DB/library internals) to clients.
        raise safe_internal_error(exc, context="run_investigation") from exc

    if result.get("status") == "guardrail_rejected":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "input_guardrail_rejected",
                "reason": (result.get("guardrail") or {}).get("reason")
                or "Input rejected by guardrails",
                "investigation_id": result.get("investigation_id"),
            },
        )

    factory = get_owner_session_factory(settings.database_url_sync)
    with factory() as session:
        apply_tenant_session(session, tenant.tenant_id)
        view = load_investigation_view(
            session, uuid.UUID(result["investigation_id"]), tenant_id=tenant.tenant_id
        )
    view["run"] = {
        "node_trace": result.get("node_trace"),
        "finding_count": result.get("finding_count"),
        "errors": result.get("errors"),
        "retry_count": result.get("retry_count"),
    }
    return sanitize_output_payload(view)


@router.get("/{investigation_id}")
def get_investigation(
    investigation_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    try:
        return load_investigation_view(
            session, investigation_id, tenant_id=tenant.tenant_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{investigation_id}/reviews")
def submit_investigation_review(
    investigation_id: uuid.UUID,
    body: SubmitReviewBody,
    tenant: TenantContext = Depends(require_user_session),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Operator review: approve/reject/comment. Requires a logged-in user session
    (P1-8) — reviewer identity comes from the authenticated session, never the
    request body, and API-key-only callers cannot review.

    On approve -> automatically creates CaseSummary for episodic memory (P6).
    """
    try:
        rev, case_summary = record_review(
            session,
            tenant_id=tenant.tenant_id,
            investigation_id=investigation_id,
            decision=body.decision,
            reviewer=tenant.user_email or "unknown",
            notes=body.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return sanitize_output_payload(
        {
            "review": {
                "id": str(rev.id),
                "investigation_id": str(rev.investigation_id),
                "decision": rev.decision,
                "reviewer": rev.reviewer,
                "notes": rev.notes,
                "created_at": rev.created_at.isoformat() if rev.created_at else None,
            },
            "case_promoted": case_summary is not None,
            "case_summary": (
                {
                    "id": str(case_summary.id),
                    "title": case_summary.title,
                    "confidence": case_summary.confidence,
                }
                if case_summary is not None
                else None
            ),
        }
    )


def dispose_investigation_runtime() -> None:
    reset_graph_cache()
    dispose_owner_engine()
