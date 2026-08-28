"""Pydantic schemas for agent structured outputs (P3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SqlStep(BaseModel):
    template_key: str
    params: dict[str, Any] = Field(default_factory=dict)
    purpose: str = ""


class RagStep(BaseModel):
    query: str
    purpose: str = ""


class InvestigationPlan(BaseModel):
    summary: str
    problem_window: dict[str, str]
    prior_window: dict[str, str]
    sql_steps: list[SqlStep] = Field(default_factory=list)
    rag_steps: list[RagStep] = Field(default_factory=list)


class Hypothesis(BaseModel):
    summary: str
    drivers: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    supporting_source_ids: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    decision: Literal["pass", "retry", "fail_soft"] = "pass"
    notes: str = ""
    gaps: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    summary: str
    actions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    claim_source_map: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "completed"
    assumptions: list[str] = Field(default_factory=list)