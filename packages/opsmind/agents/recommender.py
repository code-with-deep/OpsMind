"""Recommender agent — grounded final report with citation verification (P4)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from opsmind.agents.grounding_rules import compact_findings_for_llm, sql_revenue_values
from opsmind.agents.llm import LLMError, chat_json, llm_configured
from opsmind.agents.schemas import Recommendation
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState
from opsmind.grounding.verifier import (
    collect_valid_source_ids,
    sanitize_claim_source_map,
    verify_claim_source_map,
)


def _match_sources_for_claim(
    claim: str, findings: list[dict[str, Any]], valid: set[str]
) -> list[str]:
    """P1-4: Best-effort match a claim to the findings that actually support it,
    instead of attaching the same blanket citation bundle to every claim.

    Matches SQL findings whose row values are textually referenced in the claim,
    and RAG findings whose title/doc_key are referenced. Falls back to an empty
    list when nothing matches — callers should then use a documented fallback,
    not silently over-cite.
    """
    claim_lower = claim.lower()
    matched: list[str] = []
    for f in findings:
        sid = f.get("source_id")
        if not sid or sid not in valid:
            continue
        if f.get("kind") == "sql":
            for row in f.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                hit = False
                for v in row.values():
                    if v is None:
                        continue
                    v_str = str(v).lower()
                    if len(v_str) >= 3 and v_str in claim_lower:
                        matched.append(sid)
                        hit = True
                        break
                if hit:
                    break
        elif f.get("kind") == "rag":
            for h in f.get("hits") or []:
                title = str(h.get("title") or "").lower()
                doc_key = str(h.get("doc_key") or "").lower()
                title_tokens = [t for t in title.split() if len(t) > 4]
                if (title_tokens and any(t in claim_lower for t in title_tokens)) or (
                    doc_key and doc_key in claim_lower
                ):
                    matched.append(sid)
                    break

    seen: set[str] = set()
    out: list[str] = []
    for s in matched:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _sql_finding_by_purpose_kw(
    findings: list[dict[str, Any]], *keywords: str
) -> dict[str, Any] | None:
    for f in findings:
        if f.get("kind") != "sql":
            continue
        purpose = str(f.get("purpose") or "").lower()
        if any(kw in purpose for kw in keywords):
            return f
    return None


def _heuristic_recommendation(
    hypothesis: dict[str, Any],
    findings: list[dict[str, Any]],
    *,
    assumptions: list[str] | None = None,
) -> Recommendation:
    drivers = hypothesis.get("drivers") or []
    valid = collect_valid_source_ids(findings)
    source_ids = [s for s in (hypothesis.get("supporting_source_ids") or []) if s in valid]
    if not source_ids:
        source_ids = sorted(valid)

    sql_sources = [s for s in source_ids if s.startswith("sql_")]
    rag_sources = [s for s in source_ids if s.startswith("rag_")]
    if not sql_sources:
        sql_sources = [s for s in sorted(valid) if s.startswith("sql_")]
    if not rag_sources:
        rag_sources = [s for s in sorted(valid) if s.startswith("rag_")]

    # Fallback bundle only used when per-claim matching finds nothing (P1-4).
    fallback_sources = (
        (sql_sources[:2] + rag_sources[:2]) if (sql_sources and rag_sources) else source_ids[:4]
    )

    revs = sql_revenue_values(findings)
    rev_note = (
        f"SQL revenue figures observed: {revs}. "
        if revs
        else "Confirm week totals from cited SQL evidence. "
    )

    # P1-4: Only emit conditional actions whose trigger condition is actually
    # satisfied by real finding rows — never ship the full static template.
    actions = [rev_note + "Align stakeholders on problem vs prior window totals before acting."]

    inv_finding = _sql_finding_by_purpose_kw(findings, "inventory", "stockout", "low-stock")
    if inv_finding and any(
        isinstance(r, dict)
        and (
            (r.get("min_available") is not None and float(r.get("min_available") or 0) <= 2)
            or (r.get("available") is not None and float(r.get("available") or 0) <= 2)
        )
        for r in inv_finding.get("rows") or []
    ):
        actions.append(
            "Inventory findings show zero/low available stock: escalate replenishment and "
            "pause featured ads for the affected SKU."
        )

    carrier_finding = _sql_finding_by_purpose_kw(findings, "carrier")
    if carrier_finding and any(
        isinstance(r, dict) and float(r.get("late_count") or 0) > 0
        for r in carrier_finding.get("rows") or []
    ):
        actions.append(
            "Carrier late_count is elevated: divert volume to backup carriers for 48–72h "
            "per playbook."
        )

    promo_finding = _sql_finding_by_purpose_kw(findings, "promo", "campaign")
    if promo_finding and (promo_finding.get("rows") or []):
        actions.append(
            "A promo overlaps the drop window: evaluate cannibalization and reshape or end "
            "the campaign."
        )

    returns_finding = _sql_finding_by_purpose_kw(findings, "return")
    if returns_finding and any(
        isinstance(r, dict) and float(r.get("return_count") or 0) > 0
        for r in returns_finding.get("rows") or []
    ):
        actions.append(
            "Returns reason spikes are present: quarantine inventory and open a supplier "
            "ticket for the affected SKU."
        )

    claim_map = []
    for d in drivers:
        matched = _match_sources_for_claim(d, findings, valid)
        claim_map.append({"claim": d, "source_ids": matched or fallback_sources})
    if not claim_map and source_ids:
        claim_map = [
            {
                "claim": hypothesis.get("summary") or "Investigation completed with evidence.",
                "source_ids": fallback_sources or source_ids[:3],
            }
        ]

    summary = hypothesis.get("summary") or "Investigation completed with evidence-backed drivers."
    if revs and all(str(v) not in summary for v in revs[:2]):
        summary = f"{summary} SQL revenue values: {revs}."

    return Recommendation(
        summary=summary,
        actions=actions[:5],
        confidence=float(hypothesis.get("confidence") or 0.6),
        claim_source_map=claim_map,
        status="completed",
        assumptions=list(assumptions or [])
        + [
            "Assumptions labeled: recommendations are conditional on cited SQL/RAG evidence.",
            "Heuristic mode (no LLM): actions are limited to conditions confirmed by SQL rows.",
        ],
    )


def _llm_recommendation(
    question: str,
    hypothesis: dict[str, Any],
    findings: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> Recommendation:
    valid = sorted(collect_valid_source_ids(findings))
    compact = compact_findings_for_llm(findings, max_rows=40)
    system = (
        "You are the OpsMind Recommender. Return JSON with keys: summary, actions "
        "(list), confidence (0-1), claim_source_map (list of {claim, source_ids}), "
        "status='completed', assumptions (list of strings). "
        "Every claim MUST cite source_ids only from the allowed list. "
        "Never invent source_ids. Label assumptions explicitly. "
        "HARD RULES: Copy revenue dollars, cancel counts, carrier names, and SKUs ONLY from "
        "findings rows. Do not use demo placeholders (SKU-1001, FastShip) unless present in findings. "
        "Summary must include exact SQL week revenue totals when present. "
        "Findings with kind='case_memory' are prior approved investigations — use them as "
        "historical context (e.g. 'similar pattern seen in prior case') but never cite "
        "their numbers as current-period facts. Always ground actions in current SQL evidence."
    )
    user = json.dumps(
        {
            "question": question,
            "hypothesis": hypothesis,
            "allowed_source_ids": valid,
            "findings": compact,
        },
        default=str,
    )[:16000]
    raw = chat_json(
        api_key=runtime["llm_api_key"],
        api_base=runtime["llm_api_base"],
        model=runtime["llm_model_strong"],
        system=system,
        user=user,
    )
    return Recommendation.model_validate(raw)


def recommender_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    hypothesis = state.get("hypothesis") or {}
    findings = state.get("findings") or []
    assumptions = list(state.get("assumptions") or [])
    inv_id = uuid.UUID(state["investigation_id"])
    tenant_id = tenant_id_from_runtime(runtime)
    valid_ids = collect_valid_source_ids(findings)

    llm_error: str | None = None
    if llm_configured(runtime.get("llm_api_key")):
        try:
            rec = _llm_recommendation(state["question"], hypothesis, findings, runtime)
        except LLMError as exc:
            # P1-6: log + surface the degradation instead of silently swallowing it.
            llm_error = str(exc)
            logger.warning(
                "recommender_llm_fallback investigation_id=%s model=%s error=%s",
                inv_id, runtime.get("llm_model_strong"), exc,
            )
            rec = _heuristic_recommendation(
                hypothesis, findings, assumptions=assumptions
            )
            rec = rec.model_copy(update={"degraded": True})
        except Exception as exc:  # noqa: BLE001 — schema validation / unexpected shape
            llm_error = str(exc)
            logger.warning(
                "recommender_llm_fallback investigation_id=%s model=%s error=%s",
                inv_id, runtime.get("llm_model_strong"), exc,
            )
            rec = _heuristic_recommendation(
                hypothesis, findings, assumptions=assumptions
            )
            rec = rec.model_copy(update={"degraded": True})
    else:
        rec = _heuristic_recommendation(hypothesis, findings, assumptions=assumptions)
        rec = rec.model_copy(update={"degraded": True})

    # Citation gate: never ship unknown source_ids or numeric claims unsupported
    # by the cited SQL evidence (P1-4/P1-5).
    verification = verify_claim_source_map(rec.claim_source_map, valid_ids, findings=findings)
    if not verification.ok:
        cleaned_map = sanitize_claim_source_map(rec.claim_source_map, valid_ids)
        if cleaned_map:
            rec = rec.model_copy(
                update={
                    "claim_source_map": cleaned_map,
                    "assumptions": list(rec.assumptions)
                    + [
                        "Citation verifier removed unknown source_ids before release.",
                    ],
                }
            )
            verification = verify_claim_source_map(
                rec.claim_source_map, valid_ids, findings=findings
            )

    if not verification.ok:
        # Block ungrounded recommendation from shipping.
        blocked = {
            "summary": "Recommendation blocked: ungrounded or unknown citations.",
            "actions": [],
            "confidence": 0.0,
            "claim_source_map": [],
            "status": "insufficient_evidence",
            "assumptions": assumptions
            + ["Citation verifier rejected the draft recommendation."],
            "verification_errors": verification.errors,
        }
        factory = get_owner_session_factory(runtime["database_url_sync"])
        with factory() as session:
            apply_tenant_session(session, tenant_id)
            write_event(
                session,
                tenant_id=tenant_id,
                investigation_id=inv_id,
                event_type="citation_verifier_blocked",
                payload={
                    "errors": verification.errors,
                    "unknown_source_ids": verification.unknown_source_ids,
                },
            )
            update_investigation(
                session,
                investigation_id=inv_id,
                recommendation=blocked,
                status="insufficient_evidence",
                confidence=0.0,
            )
        return {
            "recommendation": blocked,
            "status": "insufficient_evidence",
            "node_trace": ["recommender"],
            "errors": verification.errors,
        }

    payload = rec.model_dump()
    factory = get_owner_session_factory(runtime["database_url_sync"])
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_recommender",
            payload={
                "actions": len(rec.actions),
                "confidence": rec.confidence,
                "citation_verified": True,
                "degraded": rec.degraded,
            },
        )
        if llm_error:
            # P1-6: record the degradation as a first-class event, not silence.
            write_event(
                session,
                tenant_id=tenant_id,
                investigation_id=inv_id,
                event_type="agent_recommender_degraded",
                payload={"error": llm_error[:1000]},
            )
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="citation_verifier_passed",
            payload={"claims": len(rec.claim_source_map)},
        )
        update_investigation(
            session,
            investigation_id=inv_id,
            recommendation=payload,
            confidence=rec.confidence,
            status="completed",
        )

    out: dict[str, Any] = {
        "recommendation": payload,
        "status": "completed",
        "node_trace": ["recommender"],
    }
    if llm_error:
        out["errors"] = [f"recommender_llm_fallback: {llm_error}"]
    return out
