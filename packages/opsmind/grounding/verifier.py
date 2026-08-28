"""Citation verifier — every claim must cite real source_ids (P4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VerificationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    unknown_source_ids: list[str] = field(default_factory=list)


def collect_valid_source_ids(findings: list[dict[str, Any]]) -> set[str]:
    """Valid ids are those produced by tools and present on findings."""
    valid: set[str] = set()
    for finding in findings:
        sid = finding.get("source_id")
        if isinstance(sid, str) and sid.strip():
            valid.add(sid.strip())
        evidence = finding.get("evidence") or {}
        esid = evidence.get("source_id")
        if isinstance(esid, str) and esid.strip():
            valid.add(esid.strip())
    return valid


def verify_claim_source_map(
    claim_source_map: list[dict[str, Any]],
    valid_source_ids: set[str],
) -> VerificationResult:
    """Fail if any ops claim is missing citations or cites unknown source_ids."""
    errors: list[str] = []
    unknown: list[str] = []

    if not claim_source_map:
        return VerificationResult(
            ok=False,
            errors=["Recommendation has empty claim_source_map; ungrounded output blocked."],
        )

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
        if not any(s in valid_source_ids for s in source_ids):
            errors.append(f"Claim has no valid source_id: {claim}")

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
