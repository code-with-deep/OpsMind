"""Recommender agent — grounded final report with citation verification (P4)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from opsmind.agents.llm import LLMError, chat_json, llm_configured
from opsmind.agents.schemas import Recommendation
from opsmind.db.session import get_owner_session_factory
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState
from opsmind.grounding.verifier import (
    collect_valid_source_ids,
    sanitize_claim_source_map,
    verify_claim_source_map,
)


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

    actions = [
        "Confirm problem-week vs prior-week revenue dip with finance stakeholders.",
        "If stockout confirmed on SKU-1001: escalate replenishment and pause featured ads.",
        "If FastShip SLA breaches elevated: divert volume to backup carriers for 48–72h.",
        "If Cable Flash Sale cannibalized mix: end or reshape the promo.",
        "If defective_seal returns spiked: quarantine inventory and open supplier ticket.",
    ]
    claim_map = []
    for d in drivers:
        claim_map.append({"claim": d, "source_ids": source_ids[:3]})
    if not claim_map and source_ids:
        claim_map = [
            {
                "claim": hypothesis.get("summary") or "Investigation completed with evidence.",
                "source_ids": source_ids[:3],
            }
        ]

    return Recommendation(
        summary=hypothesis.get("summary")
        or "Investigation completed with evidence-backed drivers.",
        actions=actions[:5],
        confidence=float(hypothesis.get("confidence") or 0.6),
        claim_source_map=claim_map,
        status="completed",
        assumptions=list(assumptions or [])
        + ["Assumptions labeled: recommendations are conditional on cited SQL/RAG evidence."],
    )


def _llm_recommendation(
    question: str,
    hypothesis: dict[str, Any],
    findings: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> Recommendation:
    valid = sorted(collect_valid_source_ids(findings))
    system = (
        "You are the OpsMind Recommender. Return JSON with keys: summary, actions "
        "(list), confidence (0-1), claim_source_map (list of {claim, source_ids}), "
        "status='completed', assumptions (list of strings). "
        "Every claim MUST cite source_ids only from the allowed list. "
        "Never invent source_ids. Label assumptions explicitly."
    )
    user = json.dumps(
        {
            "question": question,
            "hypothesis": hypothesis,
            "allowed_source_ids": valid,
            "finding_count": len(findings),
        },
        default=str,
    )
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
    valid_ids = collect_valid_source_ids(findings)

    if llm_configured(runtime.get("llm_api_key")):
        try:
            rec = _llm_recommendation(state["question"], hypothesis, findings, runtime)
        except (LLMError, Exception):
            rec = _heuristic_recommendation(
                hypothesis, findings, assumptions=assumptions
            )
    else:
        rec = _heuristic_recommendation(hypothesis, findings, assumptions=assumptions)

    # Citation gate: never ship unknown source_ids.
    verification = verify_claim_source_map(rec.claim_source_map, valid_ids)
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
            verification = verify_claim_source_map(rec.claim_source_map, valid_ids)

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
            write_event(
                session,
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
        write_event(
            session,
            investigation_id=inv_id,
            event_type="agent_recommender",
            payload={
                "actions": len(rec.actions),
                "confidence": rec.confidence,
                "citation_verified": True,
            },
        )
        write_event(
            session,
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

    return {
        "recommendation": payload,
        "status": "completed",
        "node_trace": ["recommender"],
    }
