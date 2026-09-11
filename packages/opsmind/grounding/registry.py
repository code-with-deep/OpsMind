"""In-process source_id registry for findings (P2 stub; verifier lands in P4)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any

# P2-10: `default_registry` below is a process-wide singleton that every SQL/RAG
# tool call registers into and NOTHING reads back — actual citation verification
# (grounding/verifier.py) derives its valid-source-id set from `findings` in
# graph state, not from this registry. Left unbounded, it grew for the life of
# the process. Bounded to an LRU-style cap so it can't leak memory even though
# it currently has no functional reader (kept for tests / future consumers).
_MAX_RECORDS = 10_000


@dataclass
class SourceRecord:
    source_id: str
    kind: str
    ref: dict[str, Any]


class SourceIdRegistry:
    """Maps source_id → tool result metadata so claims can be verified later."""

    def __init__(self, max_records: int = _MAX_RECORDS) -> None:
        self._lock = Lock()
        self._max_records = max_records
        self._records: "OrderedDict[str, SourceRecord]" = OrderedDict()

    def register(self, source_id: str, kind: str, ref: dict[str, Any]) -> SourceRecord:
        record = SourceRecord(source_id=source_id, kind=kind, ref=ref)
        with self._lock:
            self._records[source_id] = record
            self._records.move_to_end(source_id)
            while len(self._records) > self._max_records:
                self._records.popitem(last=False)  # evict oldest
        return record

    def get(self, source_id: str) -> SourceRecord | None:
        with self._lock:
            return self._records.get(source_id)

    def exists(self, source_id: str) -> bool:
        with self._lock:
            return source_id in self._records

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def all_ids(self) -> list[str]:
        with self._lock:
            return list(self._records.keys())


# Process-wide registry used by tools during a run (agents/Critic in later phases).
default_registry = SourceIdRegistry()
