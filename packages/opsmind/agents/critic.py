"""Critic agent — coverage scoring and retry / fail_soft decisions (P4)."""

from __future__ import annotations

import uuid
from typing import Any

from opsmind.agents.grounding_rules import numeric_mismatch_gaps
from opsmind.agents.schemas import Critique
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState


def _finding_kinds(findings: list[dict[str, Any]]) -> set[str]:
    return {str(f.get("kind") or "") for f in findings}


def _sql_findings_by_purpose_kw(
    findings: list[dict[str, Any]], *keywords: str
) -> list[dict[str, Any]]:
    out = []
    for f in findings:
        if f.get("kind") != "sql":
            continue
        purpose = str(f.get("purpose") or "").lower()
        if any(kw in purpose for kw in keywords):
            out.append(f)
    return out


def _driver_signals_from_rows(findings: list[dict[str, Any]]) -> dict[str, bool]:
    """P1-7 fix: determine real driver coverage from actual SQL row VALUES, not
    from planner-authored `purpose` labels or template-key substrings baked into
    the generic evidence claim text. Those always match their own template name
    (e.g. a `carrier_sla` finding's claim always contains "carrier"), which made
    this signal true on almost every run regardless of what the data showed.
    """

    def _num(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    inv_findings = _sql_findings_by_purpose_kw(findings, "inventory", "stockout", "low-stock")
    stockout = any(
        isinstance(r, dict)
        and (_num(r.get("min_available")) <= 2 or _num(r.get("available")) <= 2 or _num(r.get("zero_days")) > 0)
        for f in inv_findings
        for r in (f.get("rows") or [])
    )

    carrier_findings = _sql_findings_by_purpose_kw(findings, "carrier")
    carrier_sla = any(
        isinstance(r, dict) and _num(r.get("late_count")) > 0
        for f in carrier_findings
        for r in (f.get("rows") or [])
    )

    promo_findings = _sql_findings_by_purpose_kw(findings, "promo", "campaign")
    promo = any((f.get("rows") or []) for f in promo_findings)

    returns_findings = _sql_findings_by_purpose_kw(findings, "return")
    returns = any(
        isinstance(r, dict) and _num(r.get("return_count")) > 0
        for f in returns_findings
        for r in (f.get("rows") or [])
    )

    return {
        "stockout_or_inventory": stockout,
        "carrier_sla": carrier_sla,
        "promo": promo,
        "returns": returns,
    }


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
        # P1-7: signals now come from actual SQL row values (see
        # _driver_signals_from_rows), not from keyword-matching planner `purpose`
        # labels or template-key text that is guaranteed present regardless of data.
        driver_signals = _driver_signals_from_rows(findings)
        if findings and sum(1 for v in driver_signals.values() if v) < 1:
            gaps.append("missing_driver_coverage")

    gaps.extend(
        numeric_mismatch_gaps(
            hypothesis=hypothesis,
            findings=findings,
            question=question,
        )
    )

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
        "numeric_mismatch_with_sql_evidence",
        "missing_revenue_sql_totals",
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
    tenant_id = tenant_id_from_runtime(runtime)
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
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
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
