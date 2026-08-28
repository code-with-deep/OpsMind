"""LangGraph investigation state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(left or {})
    out.update(right or {})
    return out


class InvestigationState(TypedDict, total=False):
    question: str
    investigation_id: str
    time_window: dict[str, Any]
    plan: dict[str, Any]
    findings: Annotated[list[dict[str, Any]], operator.add]
    hypothesis: dict[str, Any]
    critique: dict[str, Any]
    retry_count: int
    recommendation: dict[str, Any]
    status: str
    node_trace: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    # Carries settings into nodes without global imports in tests.
    runtime: Annotated[dict[str, Any], _merge_dicts]
    assumptions: Annotated[list[str], operator.add]
