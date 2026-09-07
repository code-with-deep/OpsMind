"""Pipeline grounding: planner dates, critic numeric mismatch, heuristic synthesis."""

from __future__ import annotations

from opsmind.agents.critic import score_critique
from opsmind.agents.planner import _heuristic_plan
from opsmind.agents.synthesizer import _heuristic_hypothesis
from opsmind.tools.sql_templates import list_templates


def test_inventory_low_stock_template_registered():
    keys = {t["key"] for t in list_templates()}
    assert "inventory_low_stock" in keys


def test_heuristic_plan_uses_question_dates_not_demo_sku():
    q = (
        "Why did revenue drop in 2026-09-08 to 2026-09-14 "
        "compared to 2026-09-01 to 2026-09-07?"
    )
    plan = _heuristic_plan(q)
    assert plan.problem_window["start"] == "2026-09-08"
    assert plan.problem_window["end"] == "2026-09-14"
    assert plan.prior_window["start"] == "2026-09-01"
    assert plan.prior_window["end"] == "2026-09-07"
    keys = [s.template_key for s in plan.sql_steps]
    assert "inventory_low_stock" in keys
    assert "revenue_by_day" in keys
    assert "cancelled_orders" in keys
    assert not any(
        (s.template_key == "inventory_by_sku" and s.params.get("sku") == "SKU-1001")
        for s in plan.sql_steps
    )
    assert "SKU-1001" not in plan.summary
    assert "$" not in plan.summary or "[pending" in plan.summary


def test_heuristic_hypothesis_copies_sql_revenue():
    findings = [
        {
            "kind": "sql",
            "purpose": "Problem-week revenue totals",
            "source_id": "sql_a",
            "evidence": {"claim": "totals"},
            "rows": [{"revenue": 540.0, "cancelled_orders": 3}],
        },
        {
            "kind": "sql",
            "purpose": "Prior-week revenue totals",
            "source_id": "sql_b",
            "evidence": {"claim": "totals"},
            "rows": [{"revenue": 1350.0}],
        },
        {
            "kind": "sql",
            "purpose": "Low-stock / stockout scan in problem week",
            "source_id": "sql_c",
            "evidence": {"claim": "inventory"},
            "rows": [
                {
                    "sku": "SKU-N100",
                    "name": "Nova Pro Headphones",
                    "min_available": 0,
                    "zero_days": 5,
                }
            ],
        },
    ]
    hyp = _heuristic_hypothesis(findings)
    assert "540" in hyp.summary or any("540" in d for d in hyp.drivers)
    assert "1350" in " ".join(hyp.drivers) or "1350" in hyp.summary
    assert any("SKU-N100" in d for d in hyp.drivers)
    assert "SKU-1001" not in hyp.summary
    assert "FastShip" not in " ".join(hyp.drivers)


def test_critic_retries_on_numeric_mismatch():
    findings = [
        {
            "kind": "sql",
            "purpose": "Problem-week revenue totals",
            "rows": [{"revenue": 540.0}],
            "evidence": {"claim": "rev"},
        },
        {
            "kind": "sql",
            "purpose": "Prior-week revenue totals",
            "rows": [{"revenue": 1350.0}],
            "evidence": {"claim": "rev"},
        },
        {
            "kind": "rag",
            "purpose": "sop",
            "hits": [{"title": "stockout escalation"}],
            "evidence": {"claim": "inventory stockout playbook"},
        },
    ]
    critique = score_critique(
        findings=findings,
        hypothesis={
            "summary": "Revenue fell from $2000 to $360 due to earbuds stockout.",
            "drivers": ["Invented $360 total"],
            "gaps": [],
        },
        retry_count=0,
        max_retries=2,
        question="Why did revenue drop?",
    )
    assert critique.decision == "retry"
    assert "numeric_mismatch_with_sql_evidence" in critique.gaps


def test_critic_passes_when_summary_matches_sql():
    findings = [
        {
            "kind": "sql",
            "purpose": "Problem-week revenue totals",
            "rows": [{"revenue": 540.0}],
            "evidence": {"claim": "rev"},
        },
        {
            "kind": "sql",
            "purpose": "Prior-week revenue totals",
            "rows": [{"revenue": 1350.0}],
            "evidence": {"claim": "rev"},
        },
        {
            "kind": "rag",
            "purpose": "sop",
            "hits": [{"title": "stockout"}],
            "evidence": {"claim": "inventory stockout"},
        },
        {
            "kind": "sql",
            "purpose": "Low-stock scan",
            "rows": [{"sku": "SKU-N100", "min_available": 0, "available": 0}],
            "evidence": {"claim": "inventory"},
        },
    ]
    critique = score_critique(
        findings=findings,
        hypothesis={
            "summary": "Revenue problem week=$540.0 vs prior week=$1350.0.",
            "drivers": ["Revenue problem week=540.0 vs prior week=1350.0"],
            "gaps": [],
        },
        retry_count=0,
        max_retries=2,
        question="Why did revenue drop?",
    )
    assert critique.decision == "pass"
