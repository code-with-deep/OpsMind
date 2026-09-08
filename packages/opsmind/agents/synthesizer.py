"""Synthesizer agent — turn findings into a hypothesis."""

from __future__ import annotations

import json
import uuid
from typing import Any

from opsmind.agents.grounding_rules import compact_findings_for_llm, sql_revenue_values
from opsmind.agents.llm import LLMError, chat_json, llm_configured
from opsmind.agents.schemas import Hypothesis
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState


def _row_field(rows: list[Any], key: str) -> Any:
    for row in rows:
        if isinstance(row, dict) and key in row and row[key] is not None:
            return row[key]
    return None


def _heuristic_hypothesis(findings: list[dict[str, Any]]) -> Hypothesis:
    source_ids = [f.get("source_id") for f in findings if f.get("source_id")]
    drivers: list[str] = []
    problem_rev = None
    prior_rev = None

    for f in findings:
        purpose = (f.get("purpose") or "").lower()
        rows = f.get("rows") or []

        if f.get("kind") == "case_memory":
            # Prior approved case — surface its drivers as historical context.
            prior = f.get("prior_case") or {}
            title = (prior.get("title") or f.get("purpose") or "Prior case").strip()
            score = float(prior.get("score") or 0.0)
            drivers.append(
                f"Historical context (approved case, similarity={score:.2f}): {title}"
            )
            for d in (prior.get("drivers") or [])[:3]:
                d_str = str(d).strip()
                if d_str:
                    drivers.append(f"  ↳ {d_str}")
            continue

        if f.get("kind") != "sql":
            # Playbook hits — cite SOP themes without inventing SKUs/carriers.
            claim = ((f.get("evidence") or {}).get("claim") or "").lower()
            if "stockout" in claim or "replenish" in claim or "capacity" in claim:
                drivers.append("Playbook guidance available for stockout / capacity escalation")
            if "carrier" in claim or "sla" in claim or "delay" in claim:
                drivers.append("Playbook guidance available for carrier delay response")
            if "return" in claim or "defective" in claim:
                drivers.append("Playbook guidance available for returns / quality quarantine")
            if "campaign" in claim or "promo" in claim:
                drivers.append("Playbook guidance available for campaign / promotion management")
            continue

        is_week_total = (
            "week totals" in purpose
            or purpose.endswith("revenue totals")
            or ("revenue" in purpose and "week" in purpose and "daily" not in purpose)
        )
        if is_week_total:
            val = _row_field(rows, "revenue")
            if "prior" in purpose:
                prior_rev = val
            elif "problem" in purpose or problem_rev is None:
                problem_rev = val

        if "inventory" in purpose or "stockout" in purpose or "low-stock" in purpose:
            for row in rows[:5]:
                if not isinstance(row, dict):
                    continue
                sku = row.get("sku") or "SKU"
                name = row.get("name") or ""
                if "min_available" in row:
                    drivers.append(
                        f"Low stock on {sku} {name}: min available={row.get('min_available')}, "
                        f"zero_days={row.get('zero_days')}"
                    )
                elif row.get("available") is not None:
                    drivers.append(
                        f"Inventory {sku} {name} on {row.get('snapshot_date')}: "
                        f"available={row.get('available')}"
                    )

        if "carrier" in purpose or "sla" in purpose:
            for row in rows[:3]:
                if not isinstance(row, dict):
                    continue
                drivers.append(
                    f"Carrier {row.get('carrier')}: late={row.get('late_count')}/"
                    f"{row.get('shipments')} avg_delay_h={row.get('avg_delay_hours')}"
                )

        if "campaign" in purpose or "promo" in purpose:
            for row in rows[:3]:
                if not isinstance(row, dict):
                    continue
                drivers.append(
                    f"Campaign {row.get('name')} ({row.get('channel')}): "
                    f"discount={row.get('discount_pct')} featured={row.get('featured_sku')}"
                )

        if "return" in purpose:
            for row in rows[:3]:
                if not isinstance(row, dict):
                    continue
                drivers.append(
                    f"Returns {row.get('reason')} on {row.get('sku')}: "
                    f"count={row.get('return_count')} refund={row.get('refund_total')}"
                )

        if "cancel" in purpose:
            total_c = sum(int(r.get("cancelled_count") or 0) for r in rows if isinstance(r, dict))
            if total_c:
                drivers.append(f"Cancelled orders in window: {total_c}")

        if "sku mix" in purpose or "sku_revenue" in purpose:
            top = rows[0] if rows and isinstance(rows[0], dict) else None
            if top and "prior" not in purpose:
                drivers.append(
                    f"Top problem-week SKU by revenue: {top.get('sku')} "
                    f"({top.get('name')}) revenue={top.get('revenue')} units={top.get('units')}"
                )

    if problem_rev is not None and prior_rev is not None:
        drivers.insert(
            0,
            f"Revenue problem week=${problem_rev} vs prior week=${prior_rev}",
        )
    elif problem_rev is not None:
        drivers.insert(0, f"Problem-week revenue=${problem_rev}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for d in drivers:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    if not uniq:
        uniq = ["See SQL findings for revenue and operational drivers."]

    revs = sql_revenue_values(findings)
    summary = (
        "Evidence-based analysis from SQL and playbook findings. "
        + (f"Observed revenue figures from SQL: {revs}. " if revs else "")
        + "Drivers below copy measured rows — no invented demo SKUs."
    )

    return Hypothesis(
        summary=summary,
        drivers=uniq[:8],
        confidence=0.75 if len(uniq) >= 2 else 0.55,
        supporting_source_ids=[s for s in source_ids if s][:12],
        gaps=[] if findings else ["No findings were produced by Data/Knowledge."],
    )


def _llm_hypothesis(
    question: str, findings: list[dict[str, Any]], runtime: dict[str, Any]
) -> Hypothesis:
    compact = compact_findings_for_llm(findings, max_rows=40)
    system = (
        "You are the OpsMind Synthesizer. Return JSON with keys: summary, drivers "
        "(list of strings), confidence (0-1), supporting_source_ids (list), gaps (list). "
        "HARD RULES: Copy dollar amounts, counts, carrier names, and SKUs ONLY from "
        "findings.rows / findings.hits. Never invent numbers. Never use demo placeholders "
        "(SKU-1001, FastShip, earbuds) unless those exact tokens appear in findings. "
        "If week totals exist in SQL rows, the summary MUST state those exact revenue values. "
        "Only cite source_ids that appear in the findings. "
        "Findings with kind='case_memory' are prior approved investigations — use them as "
        "historical context to inform pattern recognition, but do NOT copy their numbers "
        "as current-period facts. Always prefer current SQL findings over case memory."
    )
    user = (
        f"Question: {question}\n\nFindings JSON:\n{json.dumps(compact, default=str)[:14000]}"
    )
    raw = chat_json(
        api_key=runtime["llm_api_key"],
        api_base=runtime["llm_api_base"],
        model=runtime["llm_model_strong"],
        system=system,
        user=user,
    )
    return Hypothesis.model_validate(raw)


def synthesizer_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    findings = state.get("findings") or []
    inv_id = uuid.UUID(state["investigation_id"])
    tenant_id = tenant_id_from_runtime(runtime)

    if llm_configured(runtime.get("llm_api_key")):
        try:
            hypothesis = _llm_hypothesis(state["question"], findings, runtime)
        except (LLMError, Exception):
            hypothesis = _heuristic_hypothesis(findings)
    else:
        hypothesis = _heuristic_hypothesis(findings)

    factory = get_owner_session_factory(runtime["database_url_sync"])
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_synthesizer",
            payload={
                "confidence": hypothesis.confidence,
                "drivers": hypothesis.drivers,
            },
        )
        update_investigation(
            session,
            investigation_id=inv_id,
            hypothesis=hypothesis.model_dump(),
            confidence=hypothesis.confidence,
        )

    return {
        "hypothesis": hypothesis.model_dump(),
        "node_trace": ["synthesizer"],
    }
