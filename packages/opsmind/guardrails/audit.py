"""Audit finalization for terminal investigation statuses (P5)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from opsmind.db.memory_models import Investigation
from opsmind.graph.events import update_investigation, write_event
from opsmind.guardrails.pii import redact_pii


def _question_fingerprint(question: str) -> str:
    return hashlib.sha256((question or "").encode("utf-8")).hexdigest()[:16]


def build_audit_record(
    *,
    question: str,
    status: str,
    node_trace: list[str] | None,
    retry_count: int,
    finding_count: int,
    tool_calls_used: int,
    max_tool_calls: int,
    errors: list[str] | None = None,
    guardrail_flags: dict[str, Any] | None = None,
    citation_verified: bool | None = None,
    tenant_id: uuid.UUID | str | None = None,
    user_id: uuid.UUID | str | None = None,
) -> dict[str, Any]:
    return {
        "question_fingerprint": _question_fingerprint(question),
        "question_redacted": redact_pii(question)[:500],
        "status": status,
        "node_trace": list(node_trace or []),
        "retry_count": retry_count,
        "finding_count": finding_count,
        "tool_calls_used": tool_calls_used,
        "max_tool_calls": max_tool_calls,
        "errors": list(errors or []),
        "guardrail_flags": guardrail_flags or {},
        "citation_verified": citation_verified,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "user_id": str(user_id) if user_id else None,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "audit_version": 2,
    }


def finalize_audit(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    audit: dict[str, Any],
) -> None:
    inv = session.get(Investigation, investigation_id)
    tenant_id = inv.tenant_id if inv is not None else None
    update_investigation(session, investigation_id=investigation_id, audit=audit)
    if tenant_id is not None:
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            event_type="audit_finalized",
            payload={
                "status": audit.get("status"),
                "tool_calls_used": audit.get("tool_calls_used"),
                "retry_count": audit.get("retry_count"),
                "citation_verified": audit.get("citation_verified"),
                "tenant_id": audit.get("tenant_id"),
                "user_id": audit.get("user_id"),
            },
        )


def ensure_investigation_has_audit(inv: Investigation) -> bool:
    return bool(getattr(inv, "audit", None))
