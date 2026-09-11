"""Budget helpers for per-run tool call limits (P5)."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class BudgetExceededError(RuntimeError):
    """Raised when a run exceeds configured tool-call budget."""


@dataclass
class BudgetState:
    tool_calls_used: int = 0
    max_tool_calls: int = 40
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def remaining(self) -> int:
        return max(0, self.max_tool_calls - self.tool_calls_used)

    def can_call(self, n: int = 1) -> bool:
        return self.tool_calls_used + n <= self.max_tool_calls

    def consume(self, n: int = 1) -> None:
        with self._lock:
            if not self.can_call(n):
                raise BudgetExceededError(
                    f"Tool budget exhausted ({self.tool_calls_used}/{self.max_tool_calls})"
                )
            self.tool_calls_used += n


# Process-local registry so parallel graph nodes share one counter
# (and so checkpoint serialization never has to pickle a Lock).
_REGISTRY: dict[str, BudgetState] = {}
_REGISTRY_LOCK = threading.Lock()


def register_run_budget(investigation_id: str, max_tool_calls: int) -> BudgetState:
    with _REGISTRY_LOCK:
        budget = BudgetState(max_tool_calls=max_tool_calls)
        _REGISTRY[str(investigation_id)] = budget
        return budget


def get_run_budget(investigation_id: str) -> BudgetState | None:
    return _REGISTRY.get(str(investigation_id))


def clear_run_budget(investigation_id: str) -> None:
    with _REGISTRY_LOCK:
        _REGISTRY.pop(str(investigation_id), None)


def consume_tool_budget(runtime: dict[str, Any], n: int = 1) -> None:
    """Consume from the run budget (registry preferred, then runtime.budget).

    P2-11: this registry is process-local — with more than one worker/replica,
    a run whose budget was registered on worker A is invisible to worker B, and
    this silently no-op'd (unenforced budget) before. It still can't enforce
    across processes without a shared store (Redis/Postgres), but it now logs
    loudly so the gap is visible in logs instead of failing silently.
    """
    inv_id = runtime.get("investigation_id")
    budget = get_run_budget(str(inv_id)) if inv_id else None
    if budget is None:
        budget = runtime.get("budget")
    if budget is None:
        logger.warning(
            "tool_budget_registry_miss investigation_id=%s — budget not enforced "
            "for this call (registry not found; likely cross-process/replica gap)",
            inv_id,
        )
        return
    budget.consume(n)
