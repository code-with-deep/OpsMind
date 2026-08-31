"""Date-range normalizer for investigation windows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# Locked to the synthetic seed calendar (see docs/SEED_SCENARIOS.md).
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
_EXPLICIT_RANGE = re.compile(
    rf"^\s*(?:from\s+)?(?P<start>{_ISO})\s*(?:to|:|–|-)\s*(?P<end>{_ISO})\s*$",
    re.IGNORECASE,
)


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
