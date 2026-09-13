"""Live change feed: Postgres LISTEN/NOTIFY fanned out to per-tenant subscribers.

Row triggers (migration 0016) publish tiny ``{table, op, id, tenant_id, ...}``
payloads on the ``opsmind_changes`` channel. One daemon thread per API process
holds a dedicated LISTEN connection and hands each notification to the asyncio
queues of that tenant's open ``/events/stream`` connections. Because NOTIFY is
delivered by Postgres, this works across API replicas and background
investigation threads without an extra message broker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("opsmind.api.realtime")

CHANNEL = "opsmind_changes"
_QUEUE_MAX = 256
_RESYNC = {"type": "resync"}


@dataclass(eq=False)
class Subscriber:
    tenant_id: str
    user_id: str | None
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=_QUEUE_MAX))


def _offer(queue: asyncio.Queue, event: dict[str, Any]) -> None:
    """Runs on the subscriber's event loop."""
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        # Slow consumer: drop the backlog and tell the client to refetch everything.
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(dict(_RESYNC))


def _psycopg_dsn(database_url: str) -> str:
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgresql+asyncpg://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url[len(prefix):]
    return database_url


class ChangeBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, set[Subscriber]] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._dsn = ""
        self.connected = False

    # ── lifecycle ────────────────────────────────────────────────────────────
    def ensure_started(self, database_url: str) -> None:
        """Start the listener lazily on the first subscriber (tests without a DB never do)."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._dsn = _psycopg_dsn(database_url)
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._listen_forever, name="opsmind-realtime", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ── subscriptions ────────────────────────────────────────────────────────
    def subscribe(self, tenant_id: Any, user_id: Any | None) -> Subscriber:
        sub = Subscriber(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None,
            loop=asyncio.get_running_loop(),
        )
        with self._lock:
            self._subs.setdefault(sub.tenant_id, set()).add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            subs = self._subs.get(sub.tenant_id)
            if subs is None:
                return
            subs.discard(sub)
            if not subs:
                del self._subs[sub.tenant_id]

    def publish(self, event: dict[str, Any]) -> None:
        tenant_id = event.get("tenant_id")
        if not tenant_id:
            return
        recipient = event.get("recipient_user_id")
        client_event = {
            "type": "change",
            "table": event.get("table"),
            "op": event.get("op"),
            "id": event.get("id"),
            "investigation_id": event.get("investigation_id"),
        }
        with self._lock:
            targets = list(self._subs.get(tenant_id, ()))
        for sub in targets:
            # Notifications are per user; everything else is tenant-wide.
            if recipient and sub.user_id != recipient:
                continue
            self._deliver(sub, client_event)

    def _broadcast_resync(self) -> None:
        with self._lock:
            targets = [s for subs in self._subs.values() for s in subs]
        for sub in targets:
            self._deliver(sub, dict(_RESYNC))

    @staticmethod
    def _deliver(sub: Subscriber, event: dict[str, Any]) -> None:
        try:
            sub.loop.call_soon_threadsafe(_offer, sub.queue, event)
        except RuntimeError:
            pass  # subscriber's loop already closed; unsubscribe happens in its finally

    # ── listener thread ──────────────────────────────────────────────────────
    def _listen_forever(self) -> None:
        import psycopg

        backoff = 1.0
        has_connected = False
        while not self._stop.is_set():
            try:
                with psycopg.connect(self._dsn, autocommit=True) as conn:
                    conn.execute(f"LISTEN {CHANNEL}")
                    self.connected = True
                    backoff = 1.0
                    if has_connected:
                        # Changes made while disconnected were missed.
                        self._broadcast_resync()
                    has_connected = True
                    logger.info("realtime listener connected")
                    while not self._stop.is_set():
                        for note in conn.notifies(timeout=5.0):
                            self._handle(note.payload)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "realtime listener disconnected; retrying in %.0fs", backoff, exc_info=True
                )
            finally:
                self.connected = False
            self._stop.wait(backoff)
            backoff = min(backoff * 2, 30.0)

    def _handle(self, payload: str) -> None:
        try:
            event = json.loads(payload)
        except ValueError:
            logger.warning("ignoring malformed realtime payload")
            return
        if isinstance(event, dict):
            self.publish(event)


broker = ChangeBroker()
