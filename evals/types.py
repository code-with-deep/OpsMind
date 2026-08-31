"""OpsMind Evaluation Suite — Types and Schemas (P7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EvalCategory = Literal[
    "root_cause",
    "knowledge",
    "abstain_unsupported",
    "abstain_clarification",
    "adversarial_guardrail",
    "adversarial_hallucination",
]


@dataclass(frozen=True)
class GoldenCase:
    id: str
    category: EvalCategory
    question: str
    expected_status: str | None = None
    expected_status_in: list[str] | None = None
    must_cite_themes: list[str] = field(default_factory=list)
    must_cite_sources_prefix: list[str] = field(default_factory=list)
    gold_sql_key: str | None = None
    gold_sql_params: dict[str, Any] = field(default_factory=dict)
    min_confidence: float | None = None
    must_abstain: bool = False
    max_tool_calls: int | None = None
    adversarial_check: str | None = None
    prohibited_claims: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldenCase:
        return cls(
            id=data["id"],
            category=data["category"],
            question=data["question"],
            expected_status=data.get("expected_status"),
            expected_status_in=data.get("expected_status_in"),
            must_cite_themes=list(data.get("must_cite_themes") or []),
            must_cite_sources_prefix=list(data.get("must_cite_sources_prefix") or []),
            gold_sql_key=data.get("gold_sql_key"),
            gold_sql_params=dict(data.get("gold_sql_params") or {}),
            min_confidence=data.get("min_confidence"),
            must_abstain=bool(data.get("must_abstain", False)),
            max_tool_calls=data.get("max_tool_calls"),
            adversarial_check=data.get("adversarial_check"),
            prohibited_claims=list(data.get("prohibited_claims") or []),
        )


@dataclass
class MetricScore:
    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: str


@dataclass
class CaseEvalResult:
    case_id: str
    category: str
    status: str
    passed: bool
    overall_score: float
    metrics: dict[str, MetricScore] = field(default_factory=dict)
    investigation_id: str | None = None
    duration_sec: float = 0.0
    raw_output: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "status": self.status,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 4),
            "duration_sec": round(self.duration_sec, 2),
            "investigation_id": self.investigation_id,
            "metrics": {
                k: {
                    "score": round(v.score, 4),
                    "passed": v.passed,
                    "details": v.details,
                }
                for k, v in self.metrics.items()
            },
            "errors": self.errors,
        }


@dataclass
class SuiteSummary:
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    average_score: float = 0.0
    category_scores: dict[str, float] = field(default_factory=dict)
    category_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    results: list[CaseEvalResult] = field(default_factory=list)
    duration_total_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.passed_cases / max(1, self.total_cases), 4),
            "average_score": round(self.average_score, 4),
            "duration_total_sec": round(self.duration_total_sec, 2),
            "category_scores": {k: round(v, 4) for k, v in self.category_scores.items()},
            "category_counts": self.category_counts,
            "results": [r.to_dict() for r in self.results],
        }
