"""Date-range normalizer for investigation windows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# Locked fallback when the question has no explicit dates (legacy demo calendar).
PROBLEM_WEEK_START = date(2026, 8, 17)
PROBLEM_WEEK_END = date(2026, 8, 23)
PRIOR_WEEK_START = date(2026, 8, 10)
PRIOR_WEEK_END = date(2026, 8, 16)


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    label: str
    expression: str

    def as_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "label": self.label,
            "expression": self.expression,
        }


_ISO = r"\d{4}-\d{2}-\d{2}"
_RANGE_SEP = r"(?:to|and|:|–|-)"
_EXPLICIT_RANGE = re.compile(
    rf"^\s*(?:from\s+)?(?P<start>{_ISO})\s*{_RANGE_SEP}\s*(?P<end>{_ISO})\s*$",
    re.IGNORECASE,
)
_INLINE_RANGE = re.compile(
    rf"(?P<start>{_ISO})\s*{_RANGE_SEP}\s*(?P<end>{_ISO})",
    re.IGNORECASE,
)
_SKU_RE = re.compile(r"\bSKU-[A-Za-z0-9_-]+\b", re.IGNORECASE)


def _week_containing(d: date) -> tuple[date, date]:
    """Monday–Sunday week containing ``d``."""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def normalize_date_range(
    expression: str,
    *,
    as_of: date | None = None,
) -> DateRange:
    """Map natural phrases / aliases to a concrete inclusive date window.

    Supported expressions:
    - ``problem_week`` / ``prior_week`` (seed-locked demo windows)
    - ``this_week`` / ``last_week`` (relative to ``as_of``, default today)
    - ``YYYY-MM-DD:YYYY-MM-DD`` or ``from YYYY-MM-DD to YYYY-MM-DD``
    """
    raw = (expression or "").strip()
    if not raw:
        raise ValueError("date expression must be a non-empty string")

    key = re.sub(r"[\s\-]+", "_", raw.lower())
    today = as_of or date.today()

    if key in {"problem_week", "problem", "target_week"}:
        return DateRange(
            PROBLEM_WEEK_START,
            PROBLEM_WEEK_END,
            "problem_week",
            raw,
        )
    if key in {"prior_week", "previous_week", "baseline_week"}:
        return DateRange(
            PRIOR_WEEK_START,
            PRIOR_WEEK_END,
            "prior_week",
            raw,
        )
    if key in {"this_week", "current_week"}:
        start, end = _week_containing(today)
        return DateRange(start, end, "this_week", raw)
    if key in {"last_week", "previous_calendar_week"}:
        start, end = _week_containing(today - timedelta(days=7))
        return DateRange(start, end, "last_week", raw)

    match = _EXPLICIT_RANGE.match(raw)
    if match:
        start = date.fromisoformat(match.group("start"))
        end = date.fromisoformat(match.group("end"))
        if end < start:
            raise ValueError(f"end date {end} is before start date {start}")
        return DateRange(start, end, "explicit", raw)

    raise ValueError(
        "Unrecognized date expression. Use problem_week, prior_week, this_week, "
        "last_week, or YYYY-MM-DD:YYYY-MM-DD"
    )


def extract_skus_from_text(text: str) -> list[str]:
    """Return unique SKU tokens in appearance order (normalized upper-case)."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _SKU_RE.finditer(text or ""):
        sku = match.group(0).upper()
        if sku not in seen:
            seen.add(sku)
            out.append(sku)
    return out


def extract_compare_windows_from_question(
    question: str,
) -> tuple[DateRange, DateRange] | None:
    """Parse problem/prior windows from an operator question when dates are explicit.

    Prefers the pattern: ``… in A to B compared to C to D`` → problem=A–B, prior=C–D.
    If only one range is present, prior is the immediately preceding equal-length window.
    """
    ranges: list[DateRange] = []
    for match in _INLINE_RANGE.finditer(question or ""):
        start = date.fromisoformat(match.group("start"))
        end = date.fromisoformat(match.group("end"))
        if end < start:
            continue
        ranges.append(
            DateRange(start, end, "explicit", f"{start.isoformat()} to {end.isoformat()}")
        )
    if not ranges:
        return None
    if len(ranges) >= 2:
        # First mentioned range is usually the problem window in OpsMind prompts.
        return ranges[0], ranges[1]
    problem = ranges[0]
    span = (problem.end - problem.start).days
    prior_end = problem.start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=span)
    prior = DateRange(
        prior_start,
        prior_end,
        "derived_prior",
        f"{prior_start.isoformat()} to {prior_end.isoformat()}",
    )
    return problem, prior
