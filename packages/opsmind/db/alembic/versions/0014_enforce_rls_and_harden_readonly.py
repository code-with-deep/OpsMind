"""P0 hardening: FORCE RLS on all tenant tables, lock down readonly role (0007 follow-up).

This migration:
1. Adds FORCE ROW LEVEL SECURITY to all tenant tables (P0-1)
2. Narrows the readonly role's grants to the allowlisted business tables only,
   when that role already exists (P0-3) — see ensure_readonly_role() in
   packages/opsmind/db/seed.py for the fresh-deployment path

Revision ID: 0014_enforce_rls_and_harden_readonly
Revises: 0013_password_reset
Create Date: 2026-09-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_enforce_rls_and_harden_readonly"
down_revision: Union[str, None] = "0013_password_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = (
    "investigations",
    "investigation_events",
    "tool_invocations",
    "findings",
    "reviews",
    "case_summaries",
    "documents",
    "document_chunks",
    "products",
    "carriers",
    "campaigns",
    "orders",
    "order_items",
    "inventory_snapshots",
    "shipments",
    "returns",
    "daily_metrics",
)

CONTROL_PLANE_TABLES = (
    "tenants",
    "users",
    "api_keys",
    "tenant_settings",
    "invite_codes",
    "access_requests",
    "notifications",
    "password_reset_tokens",
)

ALLOWLISTED_BUSINESS_TABLES = (
    "products",
    "carriers",
    "campaigns",
    "orders",
    "order_items",
    "inventory_snapshots",
    "shipments",
    "returns",
    "daily_metrics",
)


def upgrade() -> None:
    # P0-1: Add FORCE RLS to all tenant tables (policies already exist from 0007).
    # This makes RLS mandatory even for the table owner.
    for table in TENANT_TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    # P0-3: Revoke blanket SELECT from readonly role; grant only on business tables.
    # The readonly role (opsmind_readonly) was granted SELECT on ALL TABLES in 0007.
    #
    # Bug found by an actual fresh-DB end-to-end run: on a brand-new deployment
    # `alembic upgrade head` runs BEFORE `python -m opsmind.db.seed` ever does —
    # so opsmind_readonly does not exist yet at migration time, and the
    # REVOKE/GRANT statements below would fail with UndefinedObject. Skip this
    # block gracefully when the role isn't there yet; ensure_readonly_role()
    # (called from seed.py) now grants the same narrowed, allowlist-only access
    # itself, so a fresh deployment ends up correctly scoped either way — this
    # block only matters for narrowing an *existing* deployment's already-
    # created role that still has the old blanket grant.
    readonly_user = "opsmind_readonly"
    bind = op.get_bind()
    role_exists = bind.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :u"), {"u": readonly_user}
    ).scalar()

    if role_exists:
        # Revoke all access first.
        op.execute(
            sa.text(
                f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {readonly_user}"
            )
        )
        op.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"REVOKE ALL ON TABLES FROM {readonly_user}"
            )
        )

        # Grant SELECT only on allowlisted business tables.
        for table in ALLOWLISTED_BUSINESS_TABLES:
            op.execute(
                sa.text(f"GRANT SELECT ON {table} TO {readonly_user}")
            )

        # Explicitly revoke on control-plane tables in case any were already granted.
        for table in CONTROL_PLANE_TABLES:
            op.execute(
                sa.text(f"REVOKE ALL ON {table} FROM {readonly_user}")
            )
    else:
        print(
            f"[0014] Notice: role {readonly_user!r} does not exist yet — skipping "
            "grant narrowing. It will be created with correctly-scoped grants the "
            "first time `python -m opsmind.db.seed` runs."
        )


def downgrade() -> None:
    # Remove FORCE from tenant tables (keeps the policies themselves).
    for table in TENANT_TABLES:
        op.execute(
            sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        )

    # Restore the previous grants for readonly role (pre-0014 state), same
    # existence guard as upgrade() — the role may not exist at migration time.
    readonly_user = "opsmind_readonly"
    bind = op.get_bind()
    role_exists = bind.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :u"), {"u": readonly_user}
    ).scalar()
    if role_exists:
        op.execute(
            sa.text(
                f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {readonly_user}"
            )
        )
        op.execute(
            sa.text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT SELECT ON TABLES TO {readonly_user}"
            )
        )
