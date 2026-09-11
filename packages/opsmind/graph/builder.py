"""LangGraph builder — P4 self-correction + abstain routes + case memory enrichment."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from opsmind.agents.case_memory_agent import case_memory_node
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
) -> Literal["case_memory", "end"]:
    """Route to case_memory enrichment (first pass + retries) or abstain."""
    status = state.get("status") or ""
    if status in {"unsupported", "needs_clarification"}:
        return "end"
    return "case_memory"


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


def build_investigation_graph():
    """
    Pipeline:
      START → planner → case_memory → {data_investigator, knowledge} → synthesizer
            → critic → recommender / insufficient_evidence → END

    case_memory enriches every first-pass investigation with similar approved cases
    from the tenant's history.  On retries (retry_count > 0) it returns cheaply
    without re-fetching.  Critic retries route back through planner → case_memory
    → data_investigator/knowledge so the graph topology stays simple.

    P2-13: data_investigator (SQL) and knowledge (RAG) read only from `plan` and
    are independent of each other, so they fan out from case_memory in parallel
    and fan back in at synthesizer — `findings` and `node_trace` are both
    `operator.add`-reduced state channels, so LangGraph merges both branches'
    contributions correctly. (Previously ran strictly sequentially behind an
    unwired, dead `fanout` node that no edge ever pointed to.)
    """
    graph = StateGraph(InvestigationState)

    graph.add_node("planner", planner_node)
    graph.add_node("case_memory", case_memory_node)
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
        {"case_memory": "case_memory", "end": END},
    )
    # Fan out: case_memory feeds both data_investigator and knowledge in parallel.
    graph.add_edge("case_memory", "data_investigator")
    graph.add_edge("case_memory", "knowledge")
    # Fan in: synthesizer waits for both branches before running.
    graph.add_edge("data_investigator", "synthesizer")
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
