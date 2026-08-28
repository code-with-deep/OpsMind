"""LangGraph orchestration (P3+)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "build_investigation_graph",
    "run_investigation",
    "load_investigation_view",
]


def __getattr__(name: str) -> Any:
    if name == "build_investigation_graph":
        from opsmind.graph.builder import build_investigation_graph

        return build_investigation_graph
    if name in {"run_investigation", "load_investigation_view"}:
        from opsmind.graph import runner

        return getattr(runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
