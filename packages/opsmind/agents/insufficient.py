"""Terminal node when Critic abstains after max retries or budget stop."""

from __future__ import annotations

import uuid
from typing import Any

from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import update_investigation, write_event
from opsmind.graph.state import InvestigationState


def insufficient_evidence_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    inv_id = uuid.UUID(state["investigation_id"])
    tenant_id = tenant_id_from_runtime(runtime)
    critique = state.get("critique") or {}
    gaps = list(critique.get("gaps") or [])
    budget_stop = "budget_exceeded" in gaps or state.get("status") == "budget_exceeded"
    terminal = "budget_exceeded" if budget_stop else "insufficient_evidence"
    no_data = "no_data_in_window" in gaps
    window = (state.get("plan") or {}).get("problem_window") or {}
    window_text = (
        f"{window.get('start')} to {window.get('end')}"
        if window.get("start") and window.get("end")
        else "the requested dates"
    )

    assumptions = list(state.get("assumptions") or []) + [
        (
            "Assumptions labeled: tool budget exhausted before evidence was complete."
            if budget_stop
            else f"Assumptions labeled: no business data was found for {window_text}."
            if no_data
            else "Assumptions labeled: remaining gaps could not be closed within retry budget."
        ),
    ]
    recommendation = {
        "summary": (
            "Stopped: per-run tool budget exhausted."
            if budget_stop
            else f"No business data was found for {window_text}, so there is nothing to analyze yet."
            if no_data
            else "Insufficient evidence to complete a grounded recommendation."
        ),
        "actions": [
            *(
                [
                    "Ask about a date range that your uploaded data covers (see Settings → Business data).",
                    "If this period should have data, upload a CSV bundle that includes it.",
                ]
                if no_data
                else [
                    "Provide a clearer time window and metric.",
                    "Ensure business data and playbooks are available for the suspected drivers.",
                ]
            ),
            *(
                ["Increase MAX_TOOL_CALLS_PER_RUN if the investigation legitimately needs more tools."]
                if budget_stop
                else []
            ),
        ],
        "confidence": 0.2,
        "claim_source_map": [],
        "status": terminal,
        "gaps": gaps,
        "assumptions": assumptions,
    }

    factory = get_owner_session_factory(runtime["database_url_sync"])
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_insufficient_evidence",
            payload={"gaps": gaps, "status": terminal},
        )
        update_investigation(
            session,
            investigation_id=inv_id,
            status=terminal,
            recommendation=recommendation,
            confidence=0.2,
        )

    return {
        "status": terminal,
        "recommendation": recommendation,
        "node_trace": ["insufficient_evidence"],
        "assumptions": assumptions,
    }
