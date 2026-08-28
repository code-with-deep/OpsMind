"""Persist tool invocations and findings to Postgres."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from opsmind.db.memory_models import Finding, Investigation, InvestigationEvent, ToolInvocation
from opsmind.domain.evidence import Evidence


def create_investigation(
    session: Session,
    *,
    question: str,
    window_start=None,
    window_end=None,
    status: str = "open",
) -> Investigation:
    inv = Investigation(
        id=uuid.uuid4(),
        question=question,
        status=status,
        window_start=window_start,
        window_end=window_end,
    )
    session.add(inv)
    session.flush()
    session.add(
        InvestigationEvent(
            id=uuid.uuid4(),
            investigation_id=inv.id,
            event_type="investigation_created",
            payload={"question": question},
        )
    )
    session.commit()
    session.refresh(inv)
    return inv


def persist_tool_result(
    session: Session,
    *,
    investigation_id: uuid.UUID | None,
    tool_name: str,
    template_key: str | None,
    request: dict[str, Any],
    response_meta: dict[str, Any],
    result_fingerprint: str,
    row_count: int,
    latency_ms: int,
    source_id: str,
    evidence: Evidence,
) -> tuple[ToolInvocation, Finding]:
    inv_id = investigation_id
    if inv_id is None:
        # Standalone tool demos still get a durable parent investigation.
        auto = create_investigation(
            session,
            question=f"auto:{tool_name}:{template_key or 'query'}",
            status="tool_demo",
        )
        inv_id = auto.id

    invocation = ToolInvocation(
        id=uuid.uuid4(),
        investigation_id=inv_id,
        tool_name=tool_name,
        template_key=template_key,
        request=request,
        response_meta=response_meta,
        result_fingerprint=result_fingerprint,
        row_count=row_count,
        latency_ms=latency_ms,
        source_id=source_id,
    )
    session.add(invocation)
    session.flush()

    finding = Finding(
        id=uuid.uuid4(),
        investigation_id=inv_id,
        tool_invocation_id=invocation.id,
        source_id=source_id,
        claim=evidence.claim,
        confidence=evidence.confidence,
        sources=evidence.sources,
        assumptions=evidence.assumptions,
        gaps=evidence.gaps,
    )
    session.add(finding)
    session.add(
        InvestigationEvent(
            id=uuid.uuid4(),
            investigation_id=inv_id,
            event_type="tool_invocation",
            payload={
                "tool_name": tool_name,
                "template_key": template_key,
                "source_id": source_id,
                "row_count": row_count,
                "latency_ms": latency_ms,
            },
        )
    )
    session.commit()
    session.refresh(invocation)
    session.refresh(finding)
    return invocation, finding
