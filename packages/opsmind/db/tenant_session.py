"""Postgres session helpers for tenant isolation (MT1)."""

from __future__ import annotations

import uuid

from sqlalchemy import event
from sqlalchemy.orm import Session

#: NOLOGIN role created by migration 0016. The API usually connects as a
#: superuser / table owner, and those bypass RLS even under FORCE ROW LEVEL
#: SECURITY — so tenant-scoped transactions drop to this role, which the
#: tenant_isolation_* policies do apply to.
APP_ROLE = "opsmind_app"

# One round trip per transaction: set the tenant GUC, then SET LOCAL ROLE when
# the session user may assume APP_ROLE. Roles that can't (opsmind_readonly) are
# already subject to RLS, and databases not yet at 0016 skip the switch.
# Postgres 16+ separates membership from the SET option: a CREATEROLE owner
# (e.g. Supabase's `postgres`) is a MEMBER with ADMIN but may not SET ROLE until
# granted SET (migration 0019). The nested CASE keeps older servers from ever
# evaluating the 'SET' privilege name, which they don't recognise.
_APPLY_TENANT_SQL = (
    "SELECT set_config('app.tenant_id', %s, true), "
    f"CASE WHEN NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN NULL "
    "WHEN current_setting('server_version_num')::int >= 160000 THEN "
    f"CASE WHEN pg_has_role(session_user, '{APP_ROLE}', 'SET') "
    f"THEN set_config('role', '{APP_ROLE}', true) END "
    f"WHEN pg_has_role(session_user, '{APP_ROLE}', 'MEMBER') "
    f"THEN set_config('role', '{APP_ROLE}', true) END"
)


def apply_tenant_session(session: Session, tenant_id: uuid.UUID) -> None:
    """Scope every transaction of ``session`` to ``tenant_id`` under RLS.

    Both settings are transaction-local, so they are re-applied on each
    transaction begin (P0-2) — otherwise they vanish after the first commit().
    """
    tenant_id_str = str(tenant_id)

    def _apply(_session, _transaction, connection):
        connection.exec_driver_sql(_APPLY_TENANT_SQL, (tenant_id_str,))

    event.listen(session, "after_begin", _apply)

    if session.in_transaction():
        _apply(session, None, session.connection())
    else:
        session.connection()  # begins a transaction, which fires _apply


def tenant_id_from_runtime(runtime: dict) -> uuid.UUID:
    """Extract tenant_id from graph runtime — fail closed if missing."""
    raw = runtime.get("tenant_id")
    if not raw:
        raise ValueError("tenant_id missing from graph runtime")
    return uuid.UUID(str(raw))
