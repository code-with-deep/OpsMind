"""Shared evidence contract for tool findings (P2+)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Structured evidence returned by SQL/RAG tools and stored as findings."""

    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    source_id: str | None = None
