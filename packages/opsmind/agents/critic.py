"""Critic agent — coverage scoring and retry / fail_soft decisions (P4)."""

from __future__ import annotations

import uuid
from typing import Any

from opsmind.agents.schemas import Critique
from opsmind.db.session import get_owner_session_factory
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState


def _finding_kinds(findings: list[dict[str, Any]]) -> set[str]:
    return {str(f.get("kind") or "") for f in findings}


def _text_blob(findings: list[dict[str, Any]], hypothesis: dict[str, Any]) -> str:
    parts: list[str] = []
    for f in findings:
        parts.append(str(f.get("purpose") or ""))
        parts.append(str((f.get("evidence") or {}).get("claim") or ""))
        for hit in f.get("hits") or []:
            parts.append(str(hit.get("doc_key") or ""))
            parts.append(str(hit.get("title") or ""))
    parts.extend(str(d) for d in (hypothesis.get("drivers") or []))
    parts.append(str(hypothesis.get("summary") or ""))
    return " ".join(parts).lower()


def score_critique(
    *,
    findings: list[dict[str, Any]],
    hypothesis: dict[str, Any],
    retry_count: int,
    max_retries: int,
    question: str = "",
    errors: list[str] | None = None,
) -> Critique:
    """Score evidence coverage → pass | retry | fail_soft."""
    gaps: list[str] = list(hypothesis.get("gaps") or [])
    kinds = _finding_kinds(findings)
    blob = _text_blob(findings, hypothesis)
    q = (question or "").lower()
    err_blob = " ".join(errors or []).lower()

    # Budget exhaustion is terminal — do not retry.
    if "tool budget exhausted" in err_blob:
        return Critique(
            decision="fail_soft",
            notes="Tool budget exhausted; stopping without further retries.",
            gaps=["budget_exceeded"],
        )

    if not findings:
        gaps.append("No Data/Knowledge findings were produced.")
    if "sql" not in kinds:
        gaps.append("missing_sql_evidence")
    if "rag" not in kinds:
        gaps.append("missing_playbook_evidence")

    revenueish = any(k in q for k in ("revenue", "sales", "decrease", "drop"))
    if revenueish or findings:
        driver_signals = {
            "stockout_or_inventory": any(
                k in blob for k in ("stockout", "inventory", "sku-1001", "earbuds")
            ),
            "carrier_sla": any(k in blob for k in ("carrier", "sla", "fastship", "delay")),
            "promo": any(k in blob for k in ("campaign", "promo", "flash sale", "cannibal")),
            "returns": any(k in blob for k in ("return", "defective", "refund")),
        }
        if findings and sum(1 for v in driver_signals.values() if v) < 1:
            gaps.append("missing_driver_coverage")

    seen: set[str] = set()
    uniq_gaps: list[str] = []
    for g in gaps:
        if g and g not in seen:
            seen.add(g)
            uniq_gaps.append(g)

    critical = {
        "No Data/Knowledge findings were produced.",
        "missing_sql_evidence",
        "missing_playbook_evidence",
        "missing_driver_coverage",
    }
    has_critical = any(g in critical for g in uniq_gaps)

    if not has_critical:
        return Critique(
            decision="pass",
            notes="Coverage looks sufficient across SQL and playbook evidence.",
            gaps=uniq_gaps,
        )

    if retry_count < max_retries:
        return Critique(
            decision="retry",
            notes=(
                f"Evidence gaps remain (retry {retry_count + 1}/{max_retries}). "
                "Planner should target the gap list."
            ),
            gaps=uniq_gaps,
        )

    return Critique(
        decision="fail_soft",
        notes="Max critic retries reached with unresolved gaps; abstaining.",
        gaps=uniq_gaps,
    )


def critic_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    inv_id = uuid.UUID(state["investigation_id"])
    hypothesis = state.get("hypothesis") or {}
    findings = state.get("findings") or []
    retry_count = int(state.get("retry_count") or 0)
    max_retries = int(runtime.get("max_critic_retries") or 2)

    critique = score_critique(
        findings=findings,
        hypothesis=hypothesis,
        retry_count=retry_count,
        max_retries=max_retries,
        question=state.get("question") or "",
        errors=list(state.get("errors") or []),
    )

    new_retry = retry_count
    status = state.get("status") or "running"
    if critique.decision == "retry":
        new_retry = retry_count + 1
        status = "needs_retry"
    elif critique.decision == "fail_soft":
        gaps = critique.gaps or []
        status = (
            "budget_exceeded"
            if "budget_exceeded" in gaps
            else "insufficient_evidence"
        )
    elif critique.decision == "pass":
        status = "running"

    factory = get_owner_session_factory(runtime["database_url_sync"])
    with factory() as session:
        write_event(
            session,
            investigation_id=inv_id,
            event_type="agent_critic",
            payload={
                **critique.model_dump(),
                "retry_count": new_retry,
            },
        )
        update_investigation(
            session,
            investigation_id=inv_id,
            critique=critique.model_dump(),
            retry_count=new_retry,
            status=status if status != "running" else "running",
        )

    return {
        "critique": critique.model_dump(),
        "retry_count": new_retry,
        "status": status,
        "node_trace": ["critic"],
    }
