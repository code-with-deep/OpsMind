"""Synthesizer agent — turn findings into a hypothesis."""

from __future__ import annotations

import json
import uuid
from typing import Any

from opsmind.agents.llm import LLMError, chat_json, llm_configured
from opsmind.agents.schemas import Hypothesis
from opsmind.db.session import get_owner_session_factory
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState


def _heuristic_hypothesis(findings: list[dict[str, Any]]) -> Hypothesis:
    source_ids = [f.get("source_id") for f in findings if f.get("source_id")]
    drivers: list[str] = []
    for f in findings:
        purpose = (f.get("purpose") or "").lower()
        claim = ((f.get("evidence") or {}).get("claim") or "").lower()
        if "stockout" in purpose or "inventory" in purpose or "sku-1001" in claim:
            drivers.append("Top-seller stockout (SKU-1001 Wireless Earbuds Pro)")
        if "carrier" in purpose or "sla" in purpose:
            drivers.append("Elevated carrier SLA breaches (FastShip Express)")
        if "campaign" in purpose or "promo" in purpose:
            drivers.append("Promo cannibalization from Cable Flash Sale")
        if "return" in purpose:
            drivers.append("Returns quality issues (e.g. defective_seal)")
        if "revenue" in purpose and "prior" in purpose:
            drivers.append("Confirmed revenue decline vs prior week")

    seen: set[str] = set()
    uniq: list[str] = []
    for d in drivers:
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    if not uniq:
        uniq = ["Revenue declined in the problem week; see SQL findings for drivers."]

    return Hypothesis(
        summary=(
            "Revenue dropped in the problem week versus the prior week. "
            "Likely drivers include stockout, carrier delays, promo mix shift, "
            "and/or returns quality issues."
        ),
        drivers=uniq[:6],
        confidence=0.75 if len(uniq) >= 2 else 0.55,
        supporting_source_ids=[s for s in source_ids if s][:12],
        gaps=[] if findings else ["No findings were produced by Data/Knowledge."],
    )


def _llm_hypothesis(
    question: str, findings: list[dict[str, Any]], runtime: dict[str, Any]
) -> Hypothesis:
    compact = [
        {
            "purpose": f.get("purpose"),
            "kind": f.get("kind"),
            "source_id": f.get("source_id"),
            "claim": (f.get("evidence") or {}).get("claim"),
            "rows": f.get("rows"),
            "hits": f.get("hits"),
        }
        for f in findings
    ]
    system = (
        "You are the OpsMind Synthesizer. Return JSON with keys: summary, drivers "
        "(list of strings), confidence (0-1), supporting_source_ids (list), gaps (list). "
        "Only cite source_ids that appear in the findings."
    )
    user = (
        f"Question: {question}\n\nFindings JSON:\n{json.dumps(compact, default=str)[:12000]}"
    )
    raw = chat_json(
        api_key=runtime["llm_api_key"],
        api_base=runtime["llm_api_base"],
        model=runtime["llm_model_strong"],
        system=system,
        user=user,
    )
    return Hypothesis.model_validate(raw)


def synthesizer_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    findings = state.get("findings") or []
    inv_id = uuid.UUID(state["investigation_id"])

    if llm_configured(runtime.get("llm_api_key")):
        try:
            hypothesis = _llm_hypothesis(state["question"], findings, runtime)
        except (LLMError, Exception):
            hypothesis = _heuristic_hypothesis(findings)
    else:
        hypothesis = _heuristic_hypothesis(findings)

    factory = get_owner_session_factory(runtime["database_url_sync"])
    with factory() as session:
        write_event(
            session,
            investigation_id=inv_id,
            event_type="agent_synthesizer",
            payload={
                "confidence": hypothesis.confidence,
                "drivers": hypothesis.drivers,
            },
        )
        update_investigation(
            session,
            investigation_id=inv_id,
            hypothesis=hypothesis.model_dump(),
            confidence=hypothesis.confidence,
        )

    return {
        "hypothesis": hypothesis.model_dump(),
        "node_trace": ["synthesizer"],
    }
