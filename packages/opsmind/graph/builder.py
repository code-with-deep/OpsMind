"""LangGraph builder — P4 self-correction + abstain routes."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from opsmind.agents.critic import critic_node
from opsmind.agents.data_investigator import data_investigator_node
from opsmind.agents.insufficient import insufficient_evidence_node
from opsmind.agents.knowledge import knowledge_node
from opsmind.agents.planner import planner_node
from opsmind.agents.recommender import recommender_node
from opsmind.agents.synthesizer import synthesizer_node
from opsmind.graph.state import InvestigationState


def _route_after_planner(
    state: InvestigationState,
) -> Literal["data_investigator", "end"]:
    status = state.get("status") or ""
    if status in {"unsupported", "needs_clarification"}:
        return "end"
    return "data_investigator"


def _route_after_critic(
    state: InvestigationState,
) -> Literal["recommender", "planner", "insufficient"]:
    critique = state.get("critique") or {}
    decision = critique.get("decision") or "pass"
    if decision == "pass":
        return "recommender"
    if decision == "retry":
        return "planner"
    return "insufficient"


def _fanout_passthrough(state: InvestigationState) -> dict[str, Any]:
    """No-op join point so conditional planner can fan out to Data + Knowledge."""
    return {}


def build_investigation_graph():
    """Planner triage → tools fan-out → synth → critic loop → recommender/abstain."""
    graph = StateGraph(InvestigationState)

    graph.add_node("planner", planner_node)
    graph.add_node("fanout", _fanout_passthrough)
    graph.add_node("data_investigator", data_investigator_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("recommender", recommender_node)
    graph.add_node("insufficient_evidence", insufficient_evidence_node)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"data_investigator": "data_investigator", "end": END},
    )
    graph.add_edge("data_investigator", "knowledge")
    graph.add_edge("knowledge", "synthesizer")
    graph.add_edge("synthesizer", "critic")
    graph.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "recommender": "recommender",
            "planner": "planner",
            "insufficient": "insufficient_evidence",
        },
    )
    graph.add_edge("recommender", END)
    graph.add_edge("insufficient_evidence", END)

    return graph
