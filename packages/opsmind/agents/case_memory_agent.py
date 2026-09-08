"""Case Memory agent — retrieve similar approved cases and inject as findings."""

from __future__ import annotations

import uuid
from typing import Any

from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import write_event
from opsmind.graph.state import InvestigationState
# NOTE: query_similar_cases is imported inside the function body to break the
# circular import chain:
#   builder → case_memory_agent → memory.persist → tools.embeddings
#                                → tools.rag_tool → memory.persist  ← cycle

# Minimum cosine similarity to surface a past case (0–1).
# Too low → noise; too high → nothing surfaces for new topics.
_MIN_SCORE = 0.15

# Max cases to inject. Keep it small — each adds tokens to the LLM context.
_TOP_K = 3


def case_memory_node(state: InvestigationState) -> dict[str, Any]:
    """
    Retrieve top-K approved cases similar to the current question and inject them
    as case_memory findings.  Skipped on retry passes (findings already in state).
    """
    runtime = state.get("runtime") or {}
    question = (state.get("question") or "").strip()
    inv_id = uuid.UUID(state["investigation_id"])
    tenant_id = tenant_id_from_runtime(runtime)
    retry_count = int(state.get("retry_count") or 0)

    # On retry the planner re-routes here, but we already have findings in state.
    # Avoid re-fetching the same cases — return cheaply.
    if retry_count > 0:
        return {"node_trace": ["case_memory"]}

    # Deferred import — avoids circular dependency at module load time.
    from opsmind.memory.persist import query_similar_cases  # noqa: PLC0415

    factory = get_owner_session_factory(runtime["database_url_sync"])
    findings: list[dict[str, Any]] = []

    with factory() as session:
        apply_tenant_session(session, tenant_id)

        try:
            similar_cases = query_similar_cases(
                session,
                tenant_id=tenant_id,
                query=question,
                top_k=_TOP_K,
                min_score=_MIN_SCORE,
            )
        except Exception:  # noqa: BLE001
            # Case memory is enrichment — never block a live investigation.
            similar_cases = []

        for case in similar_cases:
            case_id = str(case["id"])
            short_id = case_id.replace("-", "")[:12]
            source_id = f"case_{short_id}"
            score = float(case.get("score") or 0.0)

            # Build a readable claim from the stored case.
            drivers_text = " | ".join(
                str(d) for d in (case.get("drivers") or [])[:4]
            )
            actions_text = " | ".join(
                str(a) for a in (case.get("actions") or [])[:3]
            )
            summary = (case.get("summary") or "").strip()
            title = (case.get("title") or "Prior case").strip()

            claim_parts = [
                f"Prior approved case (similarity {score:.2f}): {title}.",
                f"Original question: {case.get('question', '')[:120]}.",
            ]
            if summary:
                claim_parts.append(f"Finding summary: {summary}.")
            if drivers_text:
                claim_parts.append(f"Root-cause drivers: {drivers_text}.")
            if actions_text:
                claim_parts.append(f"Actions that were recommended: {actions_text}.")
            claim = " ".join(claim_parts)

            findings.append(
                {
                    "agent": "case_memory",
                    "kind": "case_memory",
                    "purpose": f"Similar approved case: {title[:60]}",
                    "source_id": source_id,
                    "evidence": {
                        "claim": claim,
                        "confidence": min(0.85, float(case.get("confidence") or 0.7)),
                        "sources": [source_id],
                        "assumptions": [
                            f"Retrieved by cosine similarity (score={score:.2f}) — "
                            "context from past approved investigation, not a guarantee of match.",
                        ],
                        "gaps": [],
                    },
                    "hits": [
                        {
                            "doc_key": case_id,
                            "title": title,
                            "score": score,
                        }
                    ],
                    # Raw case data — synthesizer and recommender can read this.
                    "prior_case": {
                        "id": case_id,
                        "title": title,
                        "question": case.get("question", ""),
                        "summary": summary,
                        "drivers": case.get("drivers") or [],
                        "actions": case.get("actions") or [],
                        "confidence": float(case.get("confidence") or 0.7),
                        "score": score,
                    },
                }
            )

        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_case_memory",
            payload={
                "similar_cases_found": len(findings),
                "case_questions": [c.get("question", "")[:80] for c in similar_cases],
                "scores": [round(c.get("score", 0), 3) for c in similar_cases],
            },
        )

    return {
        "findings": findings,
        "node_trace": ["case_memory"],
    }
