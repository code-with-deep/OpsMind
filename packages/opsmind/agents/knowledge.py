"""Knowledge agent — retrieve playbook evidence from the plan."""

from __future__ import annotations

import uuid
from typing import Any

from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session, tenant_id_from_runtime
from opsmind.graph.events import write_event
from opsmind.graph.state import InvestigationState
from opsmind.guardrails.budget import BudgetExceededError, consume_tool_budget
from opsmind.tools.rag_tool import RagToolError, run_rag_tool


def knowledge_node(state: InvestigationState) -> dict[str, Any]:
    runtime = state.get("runtime") or {}
    plan = state.get("plan") or {}
    inv_id = uuid.UUID(state["investigation_id"])
    rag_steps = plan.get("rag_steps") or []

    findings: list[dict[str, Any]] = []
    errors: list[str] = []

    factory = get_owner_session_factory(runtime["database_url_sync"])
    tenant_id = tenant_id_from_runtime(runtime)
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_knowledge",
            payload={"rag_steps": len(rag_steps)},
        )
        for step in rag_steps:
            query = step.get("query") or ""
            try:
                consume_tool_budget(runtime)
                result = run_rag_tool(
                    query=query,
                    owner_session=session,
                    tenant_id=tenant_id,
                    investigation_id=inv_id,
                    min_score=0.01,
                )
                findings.append(
                    {
                        "agent": "knowledge",
                        "kind": "rag",
                        "purpose": step.get("purpose"),
                        "evidence": result.evidence.model_dump(),
                        "hits": [
                            {
                                "doc_key": h.doc_key,
                                "title": h.title,
                                "score": h.score,
                            }
                            for h in result.hits[:3]
                        ],
                        "source_id": result.source_id,
                    }
                )
            except BudgetExceededError as exc:
                errors.append(str(exc))
                break
            except (RagToolError, Exception) as exc:  # noqa: BLE001
                errors.append(f"rag:{query}: {exc}")

        write_event(
            session,
            tenant_id=tenant_id,
            investigation_id=inv_id,
            event_type="agent_knowledge_done",
            payload={"findings": len(findings), "errors": errors},
        )

    out: dict[str, Any] = {
        "findings": findings,
        "node_trace": ["knowledge"],
    }
    if errors:
        out["errors"] = errors
    return out
