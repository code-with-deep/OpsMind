"""Compile and run investigations with optional Postgres checkpointer."""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.orm import Session

from opsmind.db.memory_models import Investigation
from opsmind.db.session import get_owner_session_factory
from opsmind.graph.builder import build_investigation_graph
from opsmind.graph.events import update_investigation, write_event
from opsmind.guardrails.audit import build_audit_record, finalize_audit
from opsmind.guardrails.budget import (
    clear_run_budget,
    get_run_budget,
    register_run_budget,
)
from opsmind.guardrails.input import check_input_guardrails
from opsmind.guardrails.output import sanitize_output_payload
from opsmind.guardrails.pii import redact_pii
from opsmind.memory.persist import create_investigation

_checkpointer = None
_compiled = None

_TERMINAL_STATUSES = frozenset(
    {
        "completed",
        "unsupported",
        "needs_clarification",
        "insufficient_evidence",
        "budget_exceeded",
        "guardrail_rejected",
        "failed",
    }
)


def _psycopg_url(database_url_sync: str) -> str:
    return database_url_sync.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


def get_checkpointer(database_url_sync: str, *, use_postgres: bool = True):
    """Return a Postgres checkpointer when possible, else in-memory."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    if use_postgres:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            conn = _psycopg_url(database_url_sync)
            pool = ConnectionPool(
                conninfo=conn,
                max_size=5,
                kwargs={"autocommit": True, "row_factory": dict_row},
            )
            saver = PostgresSaver(pool)
            saver.setup()
            _checkpointer = saver
            return _checkpointer
        except Exception:
            # Fall back for local/unit contexts without psycopg pool readiness.
            pass

    _checkpointer = MemorySaver()
    return _checkpointer


def get_compiled_graph(database_url_sync: str, *, use_postgres_checkpoint: bool = True):
    global _compiled
    if _compiled is not None:
        return _compiled
    checkpointer = get_checkpointer(
        database_url_sync, use_postgres=use_postgres_checkpoint
    )
    _compiled = build_investigation_graph().compile(checkpointer=checkpointer)
    return _compiled


def reset_graph_cache() -> None:
    global _checkpointer, _compiled
    _checkpointer = None
    _compiled = None


def build_runtime(settings: Any, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    max_tools = int(getattr(settings, "max_tool_calls_per_run", 40))
    runtime = {
        "database_url_sync": settings.database_url_sync,
        "database_url_readonly": settings.database_url_readonly,
        "llm_api_key": settings.llm_api_key,
        "llm_api_base": settings.llm_api_base,
        "llm_model_fast": settings.llm_model_fast,
        "llm_model_strong": settings.llm_model_strong,
        "max_critic_retries": int(getattr(settings, "max_critic_retries", 2)),
        "max_tool_calls_per_run": max_tools,
        "tenant_id": None,
    }
    if overrides:
        runtime.update(overrides)
        if "max_tool_calls_per_run" in overrides:
            runtime["max_tool_calls_per_run"] = int(overrides["max_tool_calls_per_run"])
    return runtime


def _persist_audit(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    question: str,
    status: str,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    final_state: dict[str, Any] | None = None,
    guardrail_flags: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    state = final_state or {}
    runtime = state.get("runtime") or {}
    budget = get_run_budget(str(investigation_id)) or runtime.get("budget")
    tool_used = int(getattr(budget, "tool_calls_used", 0) or 0)
    max_tools = int(
        getattr(budget, "max_tool_calls", None)
        or runtime.get("max_tool_calls_per_run")
        or 40
    )
    citation_verified = None
    rec = state.get("recommendation") or {}
    if isinstance(rec, dict) and rec.get("claim_source_map"):
        citation_verified = True
    if status == "insufficient_evidence" and isinstance(rec, dict):
        if rec.get("verification_errors"):
            citation_verified = False

    resolved_tenant = tenant_id or runtime.get("tenant_id")
    resolved_user = user_id or runtime.get("user_id")

    audit = build_audit_record(
        question=question,
        status=status,
        node_trace=list(state.get("node_trace") or []),
        retry_count=int(state.get("retry_count") or 0),
        finding_count=len(state.get("findings") or []),
        tool_calls_used=tool_used,
        max_tool_calls=max_tools,
        errors=errors if errors is not None else list(state.get("errors") or []),
        guardrail_flags=guardrail_flags,
        citation_verified=citation_verified,
        tenant_id=resolved_tenant,
        user_id=resolved_user,
    )
    finalize_audit(session, investigation_id=investigation_id, audit=audit)
    return audit


def run_investigation(
    *,
    question: str,
    settings: Any,
    tenant_id: uuid.UUID,
    investigation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    use_postgres_checkpoint: bool = True,
    runtime_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create (or reuse) an investigation row and execute the LangGraph run."""
    factory = get_owner_session_factory(settings.database_url_sync)

    guard = check_input_guardrails(question)
    if not guard.allowed:
        with factory() as session:
            from opsmind.db.tenant_session import apply_tenant_session

            apply_tenant_session(session, tenant_id)
            inv = create_investigation(
                session, tenant_id=tenant_id, question=question, status="guardrail_rejected"
            )
            investigation_id = inv.id
            write_event(
                session,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                event_type="guardrail_rejected",
                payload={
                    "reason": guard.reason,
                    "rule": guard.rule,
                    "question_redacted": redact_pii(question)[:500],
                },
            )
            audit = _persist_audit(
                session,
                investigation_id=investigation_id,
                question=question,
                status="guardrail_rejected",
                tenant_id=tenant_id,
                user_id=user_id,
                final_state={"node_trace": [], "retry_count": 0, "findings": [], "errors": []},
                guardrail_flags={"input": guard.rule or "rejected", "reason": guard.reason},
                errors=[guard.reason],
            )
        return {
            "investigation_id": str(investigation_id),
            "status": "guardrail_rejected",
            "recommendation": None,
            "hypothesis": None,
            "plan": None,
            "critique": None,
            "node_trace": [],
            "finding_count": 0,
            "retry_count": 0,
            "errors": [guard.reason],
            "audit": audit,
            "guardrail": {"allowed": False, "reason": guard.reason, "rule": guard.rule},
        }

    with factory() as session:
        from opsmind.db.tenant_session import apply_tenant_session

        apply_tenant_session(session, tenant_id)
        if investigation_id is None:
            inv = create_investigation(
                session, tenant_id=tenant_id, question=question, status="running"
            )
            investigation_id = inv.id
        else:
            inv = session.get(Investigation, investigation_id)
            if inv is None or inv.tenant_id != tenant_id:
                inv = create_investigation(
                    session, tenant_id=tenant_id, question=question, status="running"
                )
                investigation_id = inv.id
            else:
                update_investigation(
                    session, investigation_id=investigation_id, status="running"
                )
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            event_type="graph_started",
            payload={"question_redacted": redact_pii(question)[:500]},
        )

    graph = get_compiled_graph(
        settings.database_url_sync, use_postgres_checkpoint=use_postgres_checkpoint
    )
    thread_id = str(investigation_id)
    runtime = build_runtime(settings, runtime_overrides)
    runtime["investigation_id"] = thread_id
    runtime["tenant_id"] = str(tenant_id)
    runtime["user_id"] = str(user_id) if user_id else None
    max_tools = int(runtime.get("max_tool_calls_per_run") or 40)
    register_run_budget(thread_id, max_tools)

    initial: dict[str, Any] = {
        "question": question,
        "investigation_id": thread_id,
        "findings": [],
        "node_trace": [],
        "errors": [],
        "assumptions": [],
        "retry_count": 0,
        "status": "running",
        "runtime": runtime,
    }
    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = graph.invoke(initial, config=config)
    except Exception as exc:  # noqa: BLE001
        with factory() as session:
            from opsmind.db.tenant_session import apply_tenant_session

            apply_tenant_session(session, tenant_id)
            update_investigation(
                session,
                investigation_id=investigation_id,
                status="failed",
            )
            write_event(
                session,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                event_type="graph_failed",
                payload={"error": redact_pii(str(exc))[:1000]},
            )
            _persist_audit(
                session,
                investigation_id=investigation_id,
                question=question,
                status="failed",
                tenant_id=tenant_id,
                user_id=user_id,
                final_state={"errors": [str(exc)], "node_trace": [], "findings": []},
                errors=[str(exc)],
            )
        clear_run_budget(thread_id)
        raise

    # Persist terminal status from graph if set.
    terminal = final_state.get("status") or "completed"
    with factory() as session:
        from opsmind.db.tenant_session import apply_tenant_session

        apply_tenant_session(session, tenant_id)
        if terminal in _TERMINAL_STATUSES:
            update_investigation(
                session,
                investigation_id=investigation_id,
                status=terminal,
            )
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            event_type="graph_completed",
            payload={
                "status": terminal,
                "node_trace": final_state.get("node_trace"),
                "retry_count": final_state.get("retry_count"),
            },
        )
        audit = _persist_audit(
            session,
            investigation_id=investigation_id,
            question=question,
            status=terminal,
            tenant_id=tenant_id,
            user_id=user_id,
            final_state=final_state,
        )
    clear_run_budget(thread_id)

    result = {
        "investigation_id": thread_id,
        "status": terminal,
        "recommendation": final_state.get("recommendation"),
        "hypothesis": final_state.get("hypothesis"),
        "plan": final_state.get("plan"),
        "critique": final_state.get("critique"),
        "node_trace": final_state.get("node_trace"),
        "finding_count": len(final_state.get("findings") or []),
        "retry_count": final_state.get("retry_count") or 0,
        "errors": final_state.get("errors") or [],
        "audit": audit,
    }
    return sanitize_output_payload(result)


def load_investigation_view(
    session: Session, investigation_id: uuid.UUID, *, tenant_id: uuid.UUID
) -> dict[str, Any]:
    inv = session.get(Investigation, investigation_id)
    if inv is None or inv.tenant_id != tenant_id:
        raise KeyError(f"Investigation {investigation_id} not found")

    events = sorted(inv.events, key=lambda e: e.created_at)
    findings = sorted(inv.findings, key=lambda f: f.created_at)
    reviews = sorted(getattr(inv, "reviews", []) or [], key=lambda r: r.created_at)
    case_summary = getattr(inv, "case_summary", None)

    view = {
        "id": str(inv.id),
        "question": inv.question,
        "status": inv.status,
        "window_start": inv.window_start.isoformat() if inv.window_start else None,
        "window_end": inv.window_end.isoformat() if inv.window_end else None,
        "confidence": inv.confidence,
        "plan": inv.plan,
        "hypothesis": inv.hypothesis,
        "critique": inv.critique,
        "recommendation": inv.recommendation,
        "retry_count": inv.retry_count,
        "audit": inv.audit,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
        "reviews": [
            {
                "id": str(r.id),
                "decision": r.decision,
                "reviewer": r.reviewer,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
        "case_summary": (
            {
                "id": str(case_summary.id),
                "title": case_summary.title,
                "summary": case_summary.summary,
                "drivers": case_summary.drivers,
                "actions": case_summary.actions,
                "confidence": case_summary.confidence,
                "created_at": case_summary.created_at.isoformat()
                if case_summary.created_at
                else None,
            }
            if case_summary is not None
            else None
        ),
        "timeline": [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "findings": [
            {
                "id": str(f.id),
                "source_id": f.source_id,
                "claim": f.claim,
                "confidence": f.confidence,
                "sources": f.sources,
                "assumptions": f.assumptions,
                "gaps": f.gaps,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in findings
        ],
    }
    return sanitize_output_payload(view)


def list_investigations_view(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List past investigations with summary metadata for the Operator Console (P6)."""
    from sqlalchemy import desc, select

    stmt = (
        select(Investigation)
        .where(Investigation.tenant_id == tenant_id)
        .order_by(desc(Investigation.created_at))
    )
    if status and status.strip():
        stmt = stmt.where(Investigation.status == status.strip())
    stmt = stmt.limit(min(max(1, limit), 100)).offset(max(0, offset))

    rows = session.scalars(stmt).all()
    out: list[dict[str, Any]] = []
    for inv in rows:
        reviews = getattr(inv, "reviews", []) or []
        latest_review = reviews[-1] if reviews else None
        out.append(
            {
                "id": str(inv.id),
                "question": inv.question,
                "status": inv.status,
                "confidence": inv.confidence,
                "retry_count": inv.retry_count,
                "window_start": inv.window_start.isoformat() if inv.window_start else None,
                "window_end": inv.window_end.isoformat() if inv.window_end else None,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
                "has_audit": bool(inv.audit),
                "review_count": len(reviews),
                "latest_review_decision": latest_review.decision if latest_review else None,
                "is_approved": bool(getattr(inv, "case_summary", None)),
            }
        )
    return sanitize_output_payload(out)

