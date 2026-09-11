"""Postgres session helpers for tenant isolation (MT1)."""

from __future__ import annotations

import uuid

from sqlalchemy import event, text
from sqlalchemy.orm import Session


def apply_tenant_session(session: Session, tenant_id: uuid.UUID) -> None:
    """Set the per-request tenant GUC used by RLS policies (P0-2 fix).

    Registers an event listener so the GUC is re-applied after every transaction
    begins. Without this, the transaction-local setting (..., true) is lost after
    the first commit(), and post-commit queries run with app.tenant_id unset.
    """
    tenant_id_str = str(tenant_id)

    def _set_tenant_guc(session_obj, transaction, connection):
        """Re-apply tenant GUC on transaction begin (P0-2)."""
        connection.exec_driver_sql(
            "SELECT set_config('app.tenant_id', %s, true)",
            (tenant_id_str,),
        )

    # Register the listener. Use `once=False` so it fires on every begin.
    event.listen(session, "after_begin", _set_tenant_guc, once=False)

    # Apply it once now for the current transaction.
    session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id_str},
    )


def tenant_id_from_runtime(runtime: dict) -> uuid.UUID:
    """Extract tenant_id from graph runtime — fail closed if missing."""
    raw = runtime.get("tenant_id")
    if not raw:
        raise ValueError("tenant_id missing from graph runtime")
    return uuid.UUID(str(raw))
