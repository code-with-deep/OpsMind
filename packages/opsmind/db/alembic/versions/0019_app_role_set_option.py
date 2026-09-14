"""Let the migration role actually switch to ``opsmind_app`` on Postgres 16+.

Postgres 16 split role membership into ADMIN / INHERIT / SET options. When a
CREATEROLE user that is not a superuser (Supabase's ``postgres``) creates a
role, it becomes a member with ADMIN only, so ``pg_has_role(..., 'MEMBER')`` is
true yet ``SET ROLE opsmind_app`` is denied. Migration 0016 therefore skipped
its grant, and tenant sessions failed with "permission denied to set role".
Grant the SET option explicitly (INHERIT stays off — the owner doesn't need the
app role's privileges implicitly). No-op before Postgres 16 and for superusers.

Revision ID: 0019_app_role_set_option
Revises: 0018_supabase_data_api_lockdown
Create Date: 2026-09-14

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_app_role_set_option"
down_revision: Union[str, None] = "0018_supabase_data_api_lockdown"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "opsmind_app"


def upgrade() -> None:
    # Nested IFs, not AND: SQL doesn't guarantee short-circuiting, and servers
    # older than 16 reject the 'SET' privilege name.
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              IF current_setting('server_version_num')::int >= 160000
                 AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                IF NOT pg_has_role(current_user, '{APP_ROLE}', 'SET') THEN
                  EXECUTE 'GRANT {APP_ROLE} TO ' || quote_ident(current_user)
                    || ' WITH INHERIT FALSE, SET TRUE';
                END IF;
              END IF;
            EXCEPTION WHEN insufficient_privilege THEN
              RAISE NOTICE 'Could not grant SET on {APP_ROLE} to %; tenant sessions will not switch role',
                current_user;
            END $$
            """
        )
    )


def downgrade() -> None:
    # Removing the SET option would silently disable tenant row-level security.
    pass
