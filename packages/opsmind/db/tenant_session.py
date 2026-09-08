"""Postgres session helpers for tenant isolation (MT1)."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def apply_tenant_session(session: Session, tenant_id: uuid.UUID) -> None:
    """Set the per-request tenant GUC used by RLS policies."""
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def tenant_id_from_runtime(runtime: dict) -> uuid.UUID:
    """Extract tenant_id from graph runtime — fail closed if missing."""
    raw = runtime.get("tenant_id")
    if not raw:
        raise ValueError("tenant_id missing from graph runtime")
    return uuid.UUID(str(raw))
