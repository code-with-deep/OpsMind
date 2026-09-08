"""Question triage for Planner — supported ops domains vs abstain (P4)."""

from __future__ import annotations

import re
from typing import Literal

Route = Literal["investigate", "unsupported", "needs_clarification"]

SUPPORTED_DOMAINS = [
    "revenue / sales trends",
    "inventory / stockouts",
    "shipping / carrier SLA",
    "promotions / campaigns",
    "returns / refunds / quality",
    "order cancellations / fulfillment",
]

_UNSUPPORTED_PATTERNS = [
    r"\bweather\b",
    r"\bforecast\b",
    r"\brecipe\b",
    r"\bcook\b",
    r"\bcooking\b",
    r"\bpoem\b",
    r"\bsong\b",
    r"\bjoke\b",
    r"\bstory\b",
    r"\blyrics\b",
    r"\bhaiku\b",
    r"\bpayroll\b",
    r"\bovertime\b",
    r"\bsalary\b",
    r"\bsalaries\b",
    r"\bhr\b",
    r"\bhuman resources\b",
    r"\bemployee\b",
    r"\bhiring\b",
    r"\bbenefits\b",
    r"\btax\b",
    r"\blegal advice\b",
]

_OPS_KEYWORDS = [
    r"\brevenue\b",
    r"\bsales\b",
    r"\binventory\b",
    r"\bstockout\b",
    r"\bstock\b",
    r"\bskus?\b",          # matches both "sku" and "skus"
    r"\bshipment\b",
    r"\bshipping\b",
    r"\bdelivery\b",
    r"\bdeliveries\b",
    r"\bcarrier\b",
    r"\bsla\b",
    r"\bdelay\b",
    r"\blate\b",
    r"\bpromo\b",
    r"\bcampaign\b",
    r"\breturn\b",
    r"\brefund\b",
    r"\border\b",
    r"\bcancel",
    r"\bfulfill",
    r"\bwarehouse\b",
    r"\becommerce\b",
    r"\be-commerce\b",
    r"\bcapacit",           # matches "capacity", "capacities"
    r"\bavailable\b",
    r"\bslots?\b",          # matches "slot", "slots"
    r"\bbacklog\b",
    r"\bthroughput\b",
    r"\bengagement\b",
    r"\bproject\b",
    r"\bclient\b",
]

_VAGUE_PATTERNS = [
    r"^why are things bad\??$",
    r"^what('s| is) wrong\??$",
    r"^help\.?$",
    r"^fix (it|this|things)\.?$",
    r"^why is (everything|stuff) (bad|broken|wrong)\??$",
    r"^something('s| is) wrong\??$",
    r"^why did (sales|revenue|orders|everything) drop yesterday\??$",
    r"^why did (sales|revenue|orders) drop\??$",
    r"^everything seems broken.*",
]


def classify_question(question: str) -> tuple[Route, str]:
    """Return (route, reason) for Planner abstain / investigate decisions."""
    q = (question or "").strip()
    if len(q) < 3:
        return "needs_clarification", "Question is empty or too short."

    lower = q.lower().strip()

    for pat in _UNSUPPORTED_PATTERNS:
        if re.search(pat, lower):
            return (
                "unsupported",
                "Question is outside OpsMind's ecommerce/warehouse operations catalog.",
            )

    for pat in _VAGUE_PATTERNS:
        if re.search(pat, lower):
            return (
                "needs_clarification",
                "Question is too ambiguous; specify metric, time window, and domain.",
            )

    ops_hits = sum(1 for pat in _OPS_KEYWORDS if re.search(pat, lower))
    if ops_hits == 0 and len(lower.split()) <= 12:
        return (
            "needs_clarification",
            "No clear operations signal; clarify what metric or process to investigate.",
        )
    if ops_hits == 0:
        return (
            "unsupported",
            "No supported ecommerce/warehouse domain detected.",
        )

    return "investigate", "Question matches supported operations domains."
