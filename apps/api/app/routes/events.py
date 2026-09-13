"""Server-Sent Events stream of tenant data changes (live console updates)."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.app.auth import require_tenant_context
from api.app.config import get_settings
from api.app.realtime import broker
from opsmind.domain.tenant import TenantContext

router = APIRouter(prefix="/events", tags=["events"])

HEARTBEAT_SECONDS = 15
# Streams end periodically so the client reconnects and credentials are
# re-checked (a revoked user or expired JWT stops receiving updates).
MAX_STREAM_SECONDS = 30 * 60


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.get("/stream")
async def stream_events(
    request: Request,
    tenant: TenantContext = Depends(require_tenant_context),
) -> StreamingResponse:
    """Push ``change`` events (``{table, op, id, investigation_id}``) for this tenant.

    Payloads carry ids only; clients refetch through the regular endpoints. A
    ``resync`` event means updates may have been missed — refetch everything.
    Consumed with fetch() streaming (EventSource can't send the auth header).
    """
    broker.ensure_started(get_settings().database_url_sync)
    sub = broker.subscribe(tenant.tenant_id, tenant.user_id)

    async def generate():
        deadline = time.monotonic() + MAX_STREAM_SECONDS
        try:
            yield _sse("ready", {"live": broker.connected})
            while time.monotonic() < deadline:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(sub.queue.get(), timeout=HEARTBEAT_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                name = event.pop("type", "change")
                yield _sse(name, event)
        finally:
            broker.unsubscribe(sub)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
