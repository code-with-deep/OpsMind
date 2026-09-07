"""Planner agent — triage + plan (+ gap-aware replans on Critic retry)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from opsmind.agents.llm import LLMError, chat_json, llm_configured
from opsmind.agents.schemas import InvestigationPlan, RagStep, SqlStep
from opsmind.agents.triage import SUPPORTED_DOMAINS, classify_question
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState
from opsmind.tools.dates import (
    PROBLEM_WEEK_END,
    PROBLEM_WEEK_START,
    PRIOR_WEEK_END,
    PRIOR_WEEK_START,
    extract_compare_windows_from_question,
    extract_skus_from_text,
    normalize_date_range,
)
from opsmind.tools.sql_templates import SQL_TEMPLATES

_ALLOWED_TEMPLATES = frozenset(SQL_TEMPLATES)
_DEMO_SKU_RE = re.compile(r"\bSKU-100[1-4]\b", re.IGNORECASE)
_MONEY_CLAIM_RE = re.compile(
    r"\$\s*[\d,]+(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+\.\d{2}\b"
)


def _windows_for_question(question: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    parsed = extract_compare_windows_from_question(question)
    if parsed:
        problem, prior = parsed
    else:
        problem = normalize_date_range("problem_week")
        prior = normalize_date_range("prior_week")
    p = {"start_date": problem.start.isoformat(), "end_date": problem.end.isoformat()}
    prior_p = {"start_date": prior.start.isoformat(), "end_date": prior.end.isoformat()}
    return (
        p,
        prior_p,
        {"start": p["start_date"], "end": p["end_date"]},
        {"start": prior_p["start_date"], "end": prior_p["end_date"]},
    )


def _strip_pre_tool_numbers(text: str) -> str:
    """Remove dollar/large numeric claims that cannot be known before tools run."""
    cleaned = _MONEY_CLAIM_RE.sub("[pending SQL]", text or "")
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _dedupe_sql_steps(steps: list[SqlStep]) -> list[SqlStep]:
    seen: set[tuple[Any, ...]] = set()
    out: list[SqlStep] = []
    for step in steps:
        sig = (
            step.template_key,
            step.params.get("start_date"),
            step.params.get("end_date"),
            step.params.get("sku"),
        )
        if sig in seen:
            continue
        seen.add(sig)
        out.append(step)
    return out


def _heuristic_plan(question: str, *, gaps: list[str] | None = None) -> InvestigationPlan:
    p, prior_p, problem_window, prior_window = _windows_for_question(question)
    gaps = gaps or []
    skus = extract_skus_from_text(question)

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
            template_key="revenue_by_day",
            params=p,
            purpose="Problem-week daily revenue series",
        ),
        SqlStep(
            template_key="sku_revenue_mix",
            params=p,
            purpose="SKU mix in problem week",
        ),
        SqlStep(
            template_key="sku_revenue_mix",
            params=prior_p,
            purpose="SKU mix in prior week",
        ),
        SqlStep(
            template_key="inventory_low_stock",
            params=p,
            purpose="Low-stock / stockout scan in problem week",
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
        SqlStep(
            template_key="cancelled_orders",
            params=p,
            purpose="Cancelled orders in problem week",
        ),
    ]
    for sku in skus[:3]:
        sql_steps.append(
            SqlStep(
                template_key="inventory_by_sku",
                params={"sku": sku, **p},
                purpose=f"Inventory check for {sku}",
            )
        )

    rag_steps = [
        RagStep(query="revenue drop investigation checklist", purpose="Investigation SOP"),
        RagStep(query="stockout escalation top seller replenishment", purpose="Stockout SOP"),
        RagStep(query="carrier delay response backup carrier SLA", purpose="Carrier SOP"),
        RagStep(query="promo cannibalization flash sale triage", purpose="Promo SOP"),
        RagStep(query="returns spike defective seal quarantine", purpose="Returns SOP"),
    ]

    if "missing_sql_evidence" in gaps or "numeric_mismatch_with_sql_evidence" in gaps:
        sql_steps = [
            SqlStep(
                template_key="revenue_by_day",
                params=prior_p,
                purpose="Prior-week daily revenue series (gap fill)",
            ),
            SqlStep(
                template_key="cancelled_orders",
                params=prior_p,
                purpose="Prior-week cancelled orders (gap fill)",
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
                template_key="inventory_low_stock",
                params=p,
                purpose="Re-check stockout driver coverage",
            )
        )
        rag_steps.append(
            RagStep(
                query="stockout escalation for top seller inventory",
                purpose="Driver coverage",
            )
        )

    summary = (
        f"Compare problem window {problem_window['start']}..{problem_window['end']} vs "
        f"prior {prior_window['start']}..{prior_window['end']}; inspect stockout, carrier SLA, "
        "promo, cancels, and returns using SQL + playbooks. Do not invent totals before tools."
    )
    if gaps:
        summary = f"Replan targeting gaps: {', '.join(gaps)}. " + summary

    return InvestigationPlan(
        summary=summary,
        problem_window=problem_window,
        prior_window=prior_window,
        sql_steps=_dedupe_sql_steps(sql_steps),
        rag_steps=rag_steps[:5],
    )


def _sanitize_llm_plan(raw: InvestigationPlan, question: str) -> InvestigationPlan:
    """Force question dates, allowlisted templates, and no pre-tool money claims."""
    p, prior_p, problem_window, prior_window = _windows_for_question(question)
    skus = set(extract_skus_from_text(question))

    sql_steps: list[SqlStep] = []
    for step in raw.sql_steps:
        key = step.template_key
        if key not in _ALLOWED_TEMPLATES:
            continue
        params = dict(step.params or {})
        # Always bind windows from the question (never trust LLM invented dates).
        if "start_date" in SQL_TEMPLATES[key].required_params:
            purpose_l = (step.purpose or "").lower()
            use_prior = "prior" in purpose_l or "baseline" in purpose_l
            window = prior_p if use_prior else p
            params["start_date"] = window["start_date"]
            params["end_date"] = window["end_date"]
        if key == "inventory_by_sku":
            sku = str(params.get("sku") or "").upper()
            if not sku:
                continue
            # Drop demo-hardcoded SKUs unless the operator named them.
            if _DEMO_SKU_RE.search(sku) and sku not in skus:
                continue
            if skus and sku not in skus:
                # Prefer SKUs mentioned in the question when present.
                continue
            params["sku"] = sku
        sql_steps.append(
            SqlStep(template_key=key, params=params, purpose=step.purpose or key)
        )

    # Ensure core revenue + discovery coverage even if the LLM omitted them.
    required = [
        ("revenue_week_totals", p, "Problem-week revenue totals"),
        ("revenue_week_totals", prior_p, "Prior-week revenue totals"),
        ("revenue_by_day", p, "Problem-week daily revenue series"),
        ("sku_revenue_mix", p, "SKU mix in problem week"),
        ("inventory_low_stock", p, "Low-stock / stockout scan in problem week"),
        ("cancelled_orders", p, "Cancelled orders in problem week"),
        ("carrier_sla", p, "Carrier late deliveries"),
        ("returns_by_reason", p, "Returns spike triage"),
    ]
    have = {(s.template_key, s.params.get("start_date"), s.params.get("end_date")) for s in sql_steps}
    for key, params, purpose in required:
        sig = (key, params.get("start_date"), params.get("end_date"))
        if sig not in have:
            sql_steps.append(SqlStep(template_key=key, params=params, purpose=purpose))
            have.add(sig)

    rag_steps = [
        RagStep(query=s.query, purpose=s.purpose)
        for s in raw.rag_steps
        if s.query and "fastship" not in (s.query or "").lower()
    ] or [
        RagStep(query="revenue drop investigation checklist", purpose="Investigation SOP"),
        RagStep(query="stockout escalation top seller replenishment", purpose="Stockout SOP"),
    ]

    summary = _strip_pre_tool_numbers(raw.summary or "")
    if not summary:
        summary = (
            f"Investigate {problem_window['start']}..{problem_window['end']} vs "
            f"{prior_window['start']}..{prior_window['end']} with SQL and playbooks."
        )

    return InvestigationPlan(
        summary=summary,
        problem_window=problem_window,
        prior_window=prior_window,
        sql_steps=_dedupe_sql_steps(sql_steps),
        rag_steps=rag_steps[:5],
    )


def _llm_plan(
    question: str, runtime: dict[str, Any], *, gaps: list[str] | None = None
) -> InvestigationPlan:
    gap_text = ", ".join(gaps or []) or "none"
    p, prior_p, problem_window, prior_window = _windows_for_question(question)
    system = (
        "You are the OpsMind Planner for ecommerce/warehouse investigations. "
        "Return JSON only matching keys: summary, problem_window{start,end}, "
        "prior_window{start,end}, sql_steps[{template_key,params,purpose}], "
        "rag_steps[{query,purpose}]. "
        "Allowed sql template_key values: revenue_week_totals, revenue_by_day, "
        "sku_revenue_mix, inventory_by_sku, inventory_low_stock, carrier_sla, "
        "campaign_activity, returns_by_reason, cancelled_orders. "
        "CRITICAL: Do NOT invent revenue totals, order counts, carrier names, or SKUs. "
        "Never put dollar amounts or quantitative claims in summary before tools run. "
        "Use inventory_low_stock for stockout discovery; use inventory_by_sku only when "
        "the operator named a specific SKU. "
        "Prefer tenant-agnostic playbook queries (no demo brand names like FastShip). "
        f"Resolved problem window: {problem_window['start']} to {problem_window['end']}; "
        f"prior window: {prior_window['start']} to {prior_window['end']}. "
        f"(Legacy fallbacks if no dates in question: problem {PROBLEM_WEEK_START}–"
        f"{PROBLEM_WEEK_END}, prior {PRIOR_WEEK_START}–{PRIOR_WEEK_END}.) "
        f"Critic gaps to address: {gap_text}."
    )
    user = (
        f"Operator question:\n{question}\n\n"
        f"Use start_date/end_date params problem={p} prior={prior_p}.\n"
        "Produce an investigation plan."
    )
    raw = chat_json(
        api_key=runtime["llm_api_key"],
        api_base=runtime["llm_api_base"],
        model=runtime["llm_model_fast"],
        system=system,
        user=user,
    )
    plan = InvestigationPlan.model_validate(raw)
    return _sanitize_llm_plan(plan, question)


def planner_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    question = state["question"]
    inv_id = uuid.UUID(state["investigation_id"])
    tenant_id = tenant_id_from_runtime(runtime)
    critique = state.get("critique") or {}
    gaps = list(critique.get("gaps") or [])
    is_retry = (state.get("status") == "needs_retry") or bool(gaps and state.get("retry_count"))

    route, reason = classify_question(question)
    assumptions = [
        "Date windows come from the question when present; otherwise seed problem/prior week aliases.",
        "Totals and drivers must come from SQL/RAG tools — planner does not invent numbers.",
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
            apply_tenant_session(session, tenant_id)
            write_event(
                session,
                tenant_id=tenant_id,
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
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_planner",
            payload={
                "plan_summary": plan.summary,
                "sql_steps": len(plan.sql_steps),
                "problem_window": plan.problem_window,
                "prior_window": plan.prior_window,
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
