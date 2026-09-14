"""Hide OpsMind tables from Supabase's auto-generated Data API.

Supabase serves the ``public`` schema over its REST/GraphQL Data API as the
``anon`` and ``authenticated`` roles (usable with the project's *public* anon
key) and grants those roles privileges on every table created there. Control
plane tables — users (password hashes), api_keys, invite_codes,
password_reset_tokens — have no row-level security, so they would be readable
over HTTPS by anyone holding the anon key. OpsMind only talks to Postgres
directly, so those roles get no access at all, including to tables created later
(e.g. LangGraph checkpoint tables). No-op on databases without those roles.

Revision ID: 0018_supabase_data_api_lockdown
Revises: 0017_resync_serial_sequences
Create Date: 2026-09-14

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_supabase_data_api_lockdown"
down_revision: Union[str, None] = "0017_resync_serial_sequences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
              api_role text;
            BEGIN
              FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
                  EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', api_role);
                  EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', api_role);
                  EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', api_role
                  );
                  EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', api_role
                  );
                END IF;
              END LOOP;
            END $$
            """
        )
    )


def downgrade() -> None:
    # Deliberately not re-granted: exposing these tables to the public anon key
    # is never a desired state.
    pass
