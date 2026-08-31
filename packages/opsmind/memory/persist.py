"""Persist tool invocations, findings, reviews, and case memory to Postgres."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from opsmind.db.memory_models import (
    CaseSummary,
    Finding,
    Investigation,
    InvestigationEvent,
    Review,
    ToolInvocation,
)
from opsmind.domain.evidence import Evidence
from opsmind.tools.embeddings import local_embed


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
    session.commit()
    session.refresh(invocation)
    session.refresh(finding)
    return invocation, finding


def record_review(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    decision: str,  # "approved", "rejected", "comment"
    reviewer: str,
    notes: str | None = None,
) -> tuple[Review, CaseSummary | None]:
    """Record operator review and conditionally promote approved runs to Case Memory (P6)."""
    inv = session.get(Investigation, investigation_id)
    if inv is None:
        raise KeyError(f"Investigation {investigation_id} not found")

    rev = Review(
        id=uuid.uuid4(),
        investigation_id=investigation_id,
        decision=decision.strip().lower(),
        reviewer=reviewer.strip() or "operator",
        notes=notes.strip() if notes else None,
    )
    session.add(rev)
    session.flush()

    session.add(
        InvestigationEvent(
            id=uuid.uuid4(),
            investigation_id=investigation_id,
            event_type="review_submitted",
            payload={
                "review_id": str(rev.id),
                "decision": rev.decision,
                "reviewer": rev.reviewer,
                "notes": rev.notes,
            },
        )
    )

    case_summary: CaseSummary | None = None
    if rev.decision == "approved":
        # Extract title & summary from recommendation / hypothesis
        rec = inv.recommendation or {}
        hyp = inv.hypothesis or {}
        summary = (
            rec.get("summary")
            or hyp.get("summary")
            or f"Approved investigation for: {inv.question}"
        )
        drivers = hyp.get("drivers") or []
        actions = rec.get("actions") or []
        confidence = float(inv.confidence or rec.get("confidence") or 0.8)

        text_for_embed = f"{inv.question}\n{summary}\n{' '.join(str(d) for d in drivers)}"
        vec = local_embed(text_for_embed)

        existing_case = session.scalar(
            select(CaseSummary).where(CaseSummary.investigation_id == investigation_id)
        )
        if existing_case:
            existing_case.review_id = rev.id
            existing_case.summary = summary
            existing_case.drivers = drivers
            existing_case.actions = actions
            existing_case.confidence = confidence
            existing_case.embedding = vec
            case_summary = existing_case
        else:
            case_summary = CaseSummary(
                id=uuid.uuid4(),
                investigation_id=investigation_id,
                review_id=rev.id,
                title=f"Case: {inv.question[:80]}",
                question=inv.question,
                summary=summary,
                drivers=drivers,
                actions=actions,
                confidence=confidence,
                embedding=vec,
            )
            session.add(case_summary)

        session.add(
            InvestigationEvent(
                id=uuid.uuid4(),
                investigation_id=investigation_id,
                event_type="case_promoted_to_memory",
                payload={
                    "case_id": str(case_summary.id),
                    "title": case_summary.title,
                    "confidence": confidence,
                },
            )
        )

    session.commit()
    session.refresh(rev)
    if case_summary is not None:
        session.refresh(case_summary)
    return rev, case_summary


def list_case_summaries(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return stored case memory summaries (P6)."""
    stmt = (
        select(CaseSummary)
        .order_by(desc(CaseSummary.created_at))
        .limit(limit)
        .offset(offset)
    )
    cases = session.scalars(stmt).all()
    return [
        {
            "id": str(c.id),
            "investigation_id": str(c.investigation_id),
            "review_id": str(c.review_id) if c.review_id else None,
            "title": c.title,
            "question": c.question,
            "summary": c.summary,
            "drivers": c.drivers,
            "actions": c.actions,
            "confidence": c.confidence,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]


def query_similar_cases(
    session: Session,
    *,
    query: str,
    top_k: int = 3,
    min_score: float = 0.1,
) -> list[dict[str, Any]]:
    """Retrieve top similar approved cases by cosine similarity."""
    q = (query or "").strip()
    if not q:
        return []
    vector = local_embed(q)
    embedding_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
    sql = text(
        """
        SELECT
            id,
            investigation_id,
            title,
            question,
            summary,
            drivers,
            actions,
            confidence,
            1 - (embedding <=> CAST(:embedding AS vector)) AS score
        FROM case_summaries
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
        """
    )
    rows = session.execute(
        sql, {"embedding": embedding_literal, "top_k": top_k}
    ).mappings().all()

    out: list[dict[str, Any]] = []
    for r in rows:
        score = float(r["score"])
        if score < min_score:
            continue
        out.append(
            {
                "id": str(r["id"]),
                "investigation_id": str(r["investigation_id"]),
                "title": r["title"],
                "question": r["question"],
                "summary": r["summary"],
                "drivers": r["drivers"],
                "actions": r["actions"],
                "confidence": float(r["confidence"]),
                "score": score,
            }
        )
    return out
