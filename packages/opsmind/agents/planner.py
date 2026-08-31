"""Planner agent — triage + plan (+ gap-aware replans on Critic retry)."""

from __future__ import annotations

import uuid
from typing import Any

from opsmind.agents.llm import LLMError, chat_json, llm_configured
from opsmind.agents.schemas import InvestigationPlan, RagStep, SqlStep
from opsmind.agents.triage import SUPPORTED_DOMAINS, classify_question
from opsmind.db.session import get_owner_session_factory
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState
from opsmind.tools.dates import (
    PROBLEM_WEEK_END,
    PROBLEM_WEEK_START,
    PRIOR_WEEK_END,
    PRIOR_WEEK_START,
    normalize_date_range,
)


def _base_windows() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    problem = normalize_date_range("problem_week")
    prior = normalize_date_range("prior_week")
    p = {
        "start_date": problem.start.isoformat(),
        "end_date": problem.end.isoformat(),
    }
    prior_p = {
        "start_date": prior.start.isoformat(),
        "end_date": prior.end.isoformat(),
    }
    return (
        p,
        prior_p,
        {"start": p["start_date"], "end": p["end_date"]},
        {"start": prior_p["start_date"], "end": prior_p["end_date"]},
    )


def _heuristic_plan(question: str, *, gaps: list[str] | None = None) -> InvestigationPlan:
    p, prior_p, problem_window, prior_window = _base_windows()
    gaps = gaps or []

    sql_steps = [
        SqlStep(
            template_key="revenue_week_totals",
            params=p,
            purpose="Problem-week revenue totals",
        ),
        SqlStep(
            template_key="revenue_week_totals",
            params=prior_p,
            purpose="Prior-week revenue totals",
        ),
        SqlStep(
            template_key="sku_revenue_mix",
            params=p,
            purpose="SKU mix in problem week",
        ),
        SqlStep(
            template_key="inventory_by_sku",
            params={"sku": "SKU-1001", **p},
            purpose="Earbuds stockout check",
        ),
        SqlStep(
            template_key="carrier_sla",
            params=p,
            purpose="Carrier late deliveries",
        ),
        SqlStep(
            template_key="campaign_activity",
            params=p,
            purpose="Active promos",
        ),
        SqlStep(
            template_key="returns_by_reason",
            params=p,
            purpose="Returns spike triage",
        ),
    ]
    rag_steps = [
        RagStep(query="revenue drop investigation checklist", purpose="Investigation SOP"),
        RagStep(query="stockout escalation top seller", purpose="Stockout SOP"),
        RagStep(query="carrier delay response FastShip", purpose="Carrier SOP"),
        RagStep(query="promo cannibalization flash sale", purpose="Promo SOP"),
        RagStep(query="returns spike defective seal triage", purpose="Returns SOP"),
    ]

    # Gap-aware replan: emphasize missing evidence types.
    if "missing_sql_evidence" in gaps:
        sql_steps = [
            SqlStep(
                template_key="revenue_by_day",
                params=p,
                purpose="Daily revenue series (gap fill)",
            ),
            SqlStep(
                template_key="cancelled_orders",
                params=p,
                purpose="Cancelled orders (gap fill)",
            ),
            *sql_steps,
        ]
    if "missing_playbook_evidence" in gaps:
        rag_steps = [
            RagStep(query="stockout escalation SOP", purpose="Gap fill stockout playbook"),
            *rag_steps,
        ]
    if "missing_driver_coverage" in gaps:
        sql_steps.append(
            SqlStep(
                template_key="inventory_by_sku",
                params={"sku": "SKU-1001", **p},
                purpose="Re-check stockout driver coverage",
            )
        )
        rag_steps.append(
            RagStep(query="stockout escalation for top seller inventory", purpose="Driver coverage")
        )

    summary = (
        "Compare problem week vs prior week revenue and inspect stockout, "
        "carrier SLA, promo, and returns drivers."
    )
    if gaps:
        summary = f"Replan targeting gaps: {', '.join(gaps)}. " + summary

    return InvestigationPlan(
        summary=summary,
        problem_window=problem_window,
        prior_window=prior_window,
        sql_steps=sql_steps,
        rag_steps=rag_steps,
    )


def _llm_plan(
    question: str, runtime: dict[str, Any], *, gaps: list[str] | None = None
) -> InvestigationPlan:
    gap_text = ", ".join(gaps or []) or "none"
    system = (
        "You are the OpsMind Planner for ecommerce/warehouse investigations. "
        "Return JSON only matching keys: summary, problem_window{start,end}, "
        "prior_window{start,end}, sql_steps[{template_key,params,purpose}], "
        "rag_steps[{query,purpose}]. "
        "Allowed sql template_key values: revenue_week_totals, revenue_by_day, "
        "sku_revenue_mix, inventory_by_sku, carrier_sla, campaign_activity, "
        "returns_by_reason, cancelled_orders. "
        f"Default problem week is {PROBLEM_WEEK_START} to {PROBLEM_WEEK_END}; "
        f"prior week is {PRIOR_WEEK_START} to {PRIOR_WEEK_END}. "
        f"Critic gaps to address: {gap_text}."
    )
    user = f"Operator question:\n{question}\n\nProduce an investigation plan."
    raw = chat_json(
        api_key=runtime["llm_api_key"],
        api_base=runtime["llm_api_base"],
        model=runtime["llm_model_fast"],
        system=system,
        user=user,
    )
    return InvestigationPlan.model_validate(raw)


def planner_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    question = state["question"]
    inv_id = uuid.UUID(state["investigation_id"])
    critique = state.get("critique") or {}
    gaps = list(critique.get("gaps") or [])
    is_retry = (state.get("status") == "needs_retry") or bool(gaps and state.get("retry_count"))

    route, reason = classify_question(question)
    assumptions = [
        "Assumptions are explicit: synthetic seed calendar may be used when dates are vague.",
    ]

    # Abstain paths — do not run tools.
    if route in {"unsupported", "needs_clarification"} and not is_retry:
        payload = {
            "route": route,
            "reason": reason,
            "supported_domains": SUPPORTED_DOMAINS,
            "assumptions": assumptions,
        }
        factory = get_owner_session_factory(runtime["database_url_sync"])
        with factory() as session:
            write_event(
                session,
                investigation_id=inv_id,
                event_type="agent_planner",
                payload=payload,
            )
            update_investigation(
                session,
                investigation_id=inv_id,
                status=route,
                recommendation={
                    "summary": reason,
                    "actions": [],
                    "confidence": 0.0,
                    "claim_source_map": [],
                    "status": route,
                    "supported_domains": SUPPORTED_DOMAINS,
                    "assumptions": assumptions,
                },
                plan=None,
            )
        return {
            "status": route,
            "plan": {},
            "recommendation": {
                "summary": reason,
                "actions": [],
                "confidence": 0.0,
                "claim_source_map": [],
                "status": route,
                "supported_domains": SUPPORTED_DOMAINS,
                "assumptions": assumptions,
            },
            "node_trace": ["planner"],
            "assumptions": assumptions,
        }

    try:
        if llm_configured(runtime.get("llm_api_key")):
            try:
                plan = _llm_plan(question, runtime, gaps=gaps if is_retry else None)
            except (LLMError, Exception):
                plan = _heuristic_plan(question, gaps=gaps if is_retry else None)
        else:
            plan = _heuristic_plan(question, gaps=gaps if is_retry else None)
    except Exception as exc:  # noqa: BLE001
        plan = _heuristic_plan(question, gaps=gaps if is_retry else None)
        err = str(exc)
    else:
        err = None

    factory = get_owner_session_factory(runtime["database_url_sync"])
    with factory() as session:
        write_event(
            session,
            investigation_id=inv_id,
            event_type="agent_planner",
            payload={
                "plan_summary": plan.summary,
                "sql_steps": len(plan.sql_steps),
                "is_retry": is_retry,
                "gaps": gaps,
                "assumptions": assumptions,
            },
        )
        update_investigation(
            session,
            investigation_id=inv_id,
            status="running",
            plan=plan.model_dump(),
            window_start=plan.problem_window.get("start"),
            window_end=plan.problem_window.get("end"),
        )

    out: dict[str, Any] = {
        "plan": plan.model_dump(),
        "time_window": {
            "problem": plan.problem_window,
            "prior": plan.prior_window,
        },
        "status": "running",
        "node_trace": ["planner"],
        "retry_count": state.get("retry_count", 0),
        "assumptions": assumptions,
    }
    if err:
        out["errors"] = [f"planner_fallback: {err}"]
    return out
