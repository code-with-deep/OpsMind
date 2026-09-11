"""Citation verifier — every claim must cite real source_ids (P4).

P1-4/P1-5 hardening: the verifier now (a) only accepts sql_/rag_ prefixed source_ids
as citable evidence (case_memory findings are context, never citations), and
(b) requires numeric claims to be supported by numbers actually present in the
cited SQL finding's rows — not merely that *some* source_id was attached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# P1-5: Only tool-produced evidence is citable. case_memory / other kinds are
# historical context and must never appear in a claim_source_map.
_CITABLE_PREFIXES = ("sql_", "rag_")

_MONEY_RE = re.compile(
    r"\$\s*(?P<dollar>\d+(?:,\d{3})*(?:\.\d+)?)"
    r"|(?<![.\d])(?P<plain>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2})(?![.\d])"
)


@dataclass
class VerificationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    unknown_source_ids: list[str] = field(default_factory=list)


def _is_citable(source_id: str) -> bool:
    return any(source_id.startswith(p) for p in _CITABLE_PREFIXES)


def collect_valid_source_ids(findings: list[dict[str, Any]]) -> set[str]:
    """Valid ids are sql_/rag_ ids produced by tools (P1-5: excludes case_memory)."""
    valid: set[str] = set()
    for finding in findings:
        sid = finding.get("source_id")
        if isinstance(sid, str) and sid.strip() and _is_citable(sid.strip()):
            valid.add(sid.strip())
        evidence = finding.get("evidence") or {}
        esid = evidence.get("source_id")
        if isinstance(esid, str) and esid.strip() and _is_citable(esid.strip()):
            valid.add(esid.strip())
    return valid


def _numbers_in_finding(finding: dict[str, Any]) -> set[float]:
    """Extract numeric values actually present in a SQL finding's rows."""
    values: set[float] = set()
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


def _claim_numbers(claim: str) -> list[float]:
    out: list[float] = []
    for match in _MONEY_RE.finditer(claim or ""):
        raw = (match.group("dollar") or match.group("plain") or "").replace(",", "")
        if not raw:
            continue
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def _close(a: float, b: float) -> bool:
    tol = max(1.0, abs(b) * 0.02)
    return abs(a - b) <= tol


def verify_claim_source_map(
    claim_source_map: list[dict[str, Any]],
    valid_source_ids: set[str],
    *,
    findings: list[dict[str, Any]] | None = None,
) -> VerificationResult:
    """Fail if any claim is missing citations, cites unknown ids, or (P1-4) states
    numbers that don't appear in any cited SQL finding's rows.

    ``findings`` is optional for backward compatibility with callers that only
    want id-existence checks; pass it to enable numeric-support verification.
    """
    errors: list[str] = []
    unknown: list[str] = []

    if not claim_source_map:
        return VerificationResult(
            ok=False,
            errors=["Recommendation has empty claim_source_map; ungrounded output blocked."],
        )

    findings_by_source_id: dict[str, dict[str, Any]] = {}
    if findings:
        for f in findings:
            sid = f.get("source_id")
            if isinstance(sid, str) and sid:
                findings_by_source_id[sid] = f
            esid = (f.get("evidence") or {}).get("source_id")
            if isinstance(esid, str) and esid:
                findings_by_source_id[esid] = f

    for idx, item in enumerate(claim_source_map):
        claim = (item.get("claim") or "").strip() or f"claim[{idx}]"
        source_ids = item.get("source_ids") or []
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"Claim has no source_ids: {claim}")
            continue
        bad = [s for s in source_ids if s not in valid_source_ids]
        if bad:
            unknown.extend(bad)
            errors.append(f"Claim cites unknown source_id(s) {bad}: {claim}")
        valid_cited = [s for s in source_ids if s in valid_source_ids]
        if not valid_cited:
            errors.append(f"Claim has no valid source_id: {claim}")
            continue

        # P1-4: Numeric claims must be supported by numbers in a cited SQL finding.
        if findings_by_source_id:
            claim_nums = [n for n in _claim_numbers(claim) if n >= 50]
            sql_cited = [s for s in valid_cited if s.startswith("sql_")]
            if claim_nums and sql_cited:
                supported_numbers: set[float] = set()
                for sid in sql_cited:
                    f = findings_by_source_id.get(sid)
                    if f:
                        supported_numbers |= _numbers_in_finding(f)
                unsupported = [
                    n for n in claim_nums if not any(_close(n, s) for s in supported_numbers)
                ]
                if unsupported:
                    errors.append(
                        f"Claim states number(s) {unsupported} not found in cited SQL "
                        f"finding rows: {claim}"
                    )

    return VerificationResult(ok=not errors, errors=errors, unknown_source_ids=unknown)


def sanitize_claim_source_map(
    claim_source_map: list[dict[str, Any]],
    valid_source_ids: set[str],
) -> list[dict[str, Any]]:
    """Drop unknown ids; drop claims that end up with zero valid citations."""
    cleaned: list[dict[str, Any]] = []
    for item in claim_source_map:
        claim = item.get("claim") or ""
        ids = [s for s in (item.get("source_ids") or []) if s in valid_source_ids]
        if ids:
            cleaned.append({"claim": claim, "source_ids": ids})
    return cleaned
