"""Specialized agents: Planner, Data, Knowledge, Synth, Critic, Recommender."""

from __future__ import annotations

from typing import Any

__all__ = [
    "planner_node",
    "data_investigator_node",
    "knowledge_node",
    "synthesizer_node",
    "critic_node",
    "recommender_node",
]

_NODE_EXPORTS = {
    "planner_node": ("opsmind.agents.planner", "planner_node"),
    "data_investigator_node": (
        "opsmind.agents.data_investigator",
        "data_investigator_node",
    ),
    "knowledge_node": ("opsmind.agents.knowledge", "knowledge_node"),
    "synthesizer_node": ("opsmind.agents.synthesizer", "synthesizer_node"),
    "critic_node": ("opsmind.agents.critic", "critic_node"),
    "recommender_node": ("opsmind.agents.recommender", "recommender_node"),
}


def __getattr__(name: str) -> Any:
    if name in _NODE_EXPORTS:
        mod_name, attr = _NODE_EXPORTS[name]
        import importlib

        return getattr(importlib.import_module(mod_name), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
