"""Helpers to keep agent narratives grounded in tool findings."""

from __future__ import annotations

import re
from typing import Any


_MONEY_RE = re.compile(
    r"\$\s*(?P<dollar>\d+(?:,\d{3})*(?:\.\d+)?)"
    r"|(?<![.\d])(?P<plain>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2})(?![.\d])"
)


def compact_findings_for_llm(findings: list[dict[str, Any]], *, max_rows: int = 30) -> list[dict[str, Any]]:
    """Shrink findings for LLM context while keeping aggregate SQL rows intact."""
    compact: list[dict[str, Any]] = []
    for finding in findings:
        rows = finding.get("rows") or []
        compact.append(
            {
                "purpose": finding.get("purpose"),
                "kind": finding.get("kind"),
                "source_id": finding.get("source_id"),
                "claim": (finding.get("evidence") or {}).get("claim"),
                "rows": rows[:max_rows],
                "hits": (finding.get("hits") or [])[:5],
            }
        )
    return compact


def sql_revenue_values(findings: list[dict[str, Any]]) -> list[float]:
    """Collect week-total revenue figures from SQL findings (not daily series rows)."""
    values: list[float] = []
    for finding in findings:
        if finding.get("kind") != "sql":
            continue
        purpose = str(finding.get("purpose") or "").lower()
        if "daily" in purpose:
            continue
        if "revenue" not in purpose and "week" not in purpose:
            continue
        rows = finding.get("rows") or []
        if not rows:
            continue
        # Prefer aggregate week totals (single row with window_start) over mix tables.
        if len(rows) == 1 and isinstance(rows[0], dict) and "revenue" in rows[0]:
            try:
                values.append(float(rows[0]["revenue"]))
            except (TypeError, ValueError):
                continue
            continue
        if "week totals" in purpose or purpose.endswith("revenue totals"):
            for row in rows:
                if not isinstance(row, dict) or row.get("revenue") is None:
                    continue
                try:
                    values.append(float(row["revenue"]))
                except (TypeError, ValueError):
                    continue
    return values


def _all_sql_numeric_values(findings: list[dict[str, Any]]) -> set[float]:
    """All numeric values present anywhere in any SQL finding's rows.

    Bug found via an actual end-to-end run: numeric_mismatch_gaps() below used
    to compare stated numbers ONLY against sql_revenue_values() (week-total
    aggregates). But the heuristic synthesizer always cites a per-SKU revenue
    figure too (e.g. "Top problem-week SKU by revenue: ... revenue=2319.42"),
    pulled straight from a real sku_revenue_mix row — that number was never in
    the narrow week-totals set, so every heuristic-mode investigation with SKU
    mix data got a false-positive "invented number" flag and was rejected into
    insufficient_evidence after burning all retries. This broader set answers
    "was this number observed anywhere in real SQL evidence" — the actual
    question the check is supposed to ask — while sql_revenue_values() stays
    narrow for the separate missing_revenue_sql_totals check below.
    """
    values: set[float] = set()
    for finding in findings:
        if finding.get("kind") != "sql":
            continue
        for row in finding.get("rows") or []:
            if not isinstance(row, dict):
                continue
            for v in row.values():
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    values.add(round(float(v), 2))
                elif isinstance(v, str):
                    try:
                        values.add(round(float(v.replace(",", "")), 2))
                    except ValueError:
                        continue
    return values


def money_mentions(text: str) -> list[float]:
    """Extract dollar-like amounts ($…, 1,350, or n.nn) — not bare years/counts."""
    values: list[float] = []
    for match in _MONEY_RE.finditer(text or ""):
        raw = (match.group("dollar") or match.group("plain") or "").replace(",", "")
        if not raw:
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def numeric_mismatch_gaps(
    *,
    hypothesis: dict[str, Any],
    findings: list[dict[str, Any]],
    question: str = "",
) -> list[str]:
    """Flag summaries that invent dollar amounts not present in SQL evidence."""
    q = (question or "").lower()
    revenueish = any(k in q for k in ("revenue", "sales", "decrease", "drop"))
    if not revenueish:
        return []

    sql_values = sql_revenue_values(findings)
    if len(sql_values) < 1:
        return ["missing_revenue_sql_totals"]

    summary = str(hypothesis.get("summary") or "")
    drivers = " ".join(str(d) for d in (hypothesis.get("drivers") or []))
    mentioned = money_mentions(summary + " " + drivers)
    if not mentioned:
        # No dollar claims yet — soft gap only for follow-up, not critical by itself.
        return []

    # Allow small rounding / formatting drift.
    def _close(a: float, b: float) -> bool:
        tol = max(1.0, abs(b) * 0.02)
        return abs(a - b) <= tol

    # Compare against ALL numbers actually present in SQL evidence (SKU mix,
    # refunds, etc.) — not just the narrow week-totals set, which produced
    # false positives on legitimate per-SKU/returns/carrier figures (see
    # _all_sql_numeric_values docstring).
    grounded_values = _all_sql_numeric_values(findings)
    unmatched = [m for m in mentioned if not any(_close(m, s) for s in grounded_values)]
    # Ignore tiny incidental numbers (percents often parsed without $ — filter large $ claims)
    unmatched_money = [m for m in unmatched if m >= 50]
    if unmatched_money:
        return ["numeric_mismatch_with_sql_evidence"]
    return []
