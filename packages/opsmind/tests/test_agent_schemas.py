"""Unit tests for agent output schemas (P3)."""

import pytest
from pydantic import ValidationError

from opsmind.agents.schemas import Critique, Hypothesis, InvestigationPlan, Recommendation


def test_plan_schema_requires_windows():
    plan = InvestigationPlan(
        summary="x",
        problem_window={"start": "2026-08-17", "end": "2026-08-23"},
        prior_window={"start": "2026-08-10", "end": "2026-08-16"},
    )
    assert plan.sql_steps == []


def test_hypothesis_confidence_bounds():
    with pytest.raises(ValidationError):
        Hypothesis(summary="x", confidence=1.5)


def test_critique_decision_enum():
    c = Critique(decision="pass", notes="ok")
    assert c.decision == "pass"
    with pytest.raises(ValidationError):
        Critique(decision="explode")  # type: ignore[arg-type]


def test_recommendation_schema():
    r = Recommendation(summary="done", actions=["a"], confidence=0.7)
    assert r.status == "completed"
