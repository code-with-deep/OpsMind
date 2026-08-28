"""In-process source_id registry for findings (P2 stub; verifier lands in P4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class SourceRecord:
    source_id: str
    kind: str
    ref: dict[str, Any]


class SourceIdRegistry:
    """Maps source_id → tool result metadata so claims can be verified later."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[str, SourceRecord] = {}

    def register(self, source_id: str, kind: str, ref: dict[str, Any]) -> SourceRecord:
        record = SourceRecord(source_id=source_id, kind=kind, ref=ref)
        with self._lock:
            self._records[source_id] = record
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
