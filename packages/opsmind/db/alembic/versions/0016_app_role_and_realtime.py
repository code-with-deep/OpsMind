"""Enforce tenant isolation for the app role + realtime change notifications.

1. RLS was defined (0007) and FORCEd (0014) but never evaluated: the API connects
   as the database owner, which in the pgvector image is a superuser — and
   superusers bypass row-level security even under FORCE. This creates the
   NOLOGIN role ``opsmind_app`` with plain DML grants; tenant-scoped sessions
   ``SET LOCAL ROLE opsmind_app`` (opsmind.db.tenant_session) so the
   tenant_isolation_* policies actually apply.
2. Row triggers ``pg_notify('opsmind_changes', ...)`` on the tables the web
   console displays, so the API can push live updates to browsers
   (api.app.realtime / GET /events/stream) instead of the UI polling.

Revision ID: 0016_app_role_and_realtime
Revises: 0015_pgvector_hnsw_indexes
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_app_role_and_realtime"
down_revision: Union[str, None] = "0015_pgvector_hnsw_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "opsmind_app"
NOTIFY_CHANNEL = "opsmind_changes"

# Keep payloads tiny (ids only) — clients refetch through the normal,
# tenant-checked API. Bulk-written tables (document_chunks, business rows) are
# deliberately excluded; their parent rows (documents, ingest_jobs) notify instead.
NOTIFY_TABLES = (
    "investigations",
    "investigation_events",
    "reviews",
    "case_summaries",
    "documents",
    "ingest_jobs",
    "notifications",
    "access_requests",
    "users",
    "invite_codes",
)


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
              END IF;
            END $$
            """
        )
    )
    # A superuser may SET ROLE to anything; a non-superuser owner (managed cloud
    # Postgres) needs membership. Best effort — requires CREATEROLE/ADMIN there.
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              IF NOT pg_has_role(current_user, '{APP_ROLE}', 'MEMBER') THEN
                EXECUTE 'GRANT {APP_ROLE} TO ' || quote_ident(current_user);
              END IF;
            EXCEPTION WHEN insufficient_privilege THEN
              RAISE NOTICE 'Could not grant {APP_ROLE} to %; tenant sessions will not switch role',
                current_user;
            END $$
            """
        )
    )
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
    op.execute(
        sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    )
    # UPDATE is needed for setval(): CSV ingest re-syncs id sequences after loading rows.
    op.execute(
        sa.text(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
        )
    )

    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION opsmind_notify_change() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE
              rec jsonb;
            BEGIN
              IF TG_OP = 'DELETE' THEN
                rec := to_jsonb(OLD);
              ELSE
                rec := to_jsonb(NEW);
              END IF;
              PERFORM pg_notify(
                '{NOTIFY_CHANNEL}',
                json_build_object(
                  'table', TG_TABLE_NAME,
                  'op', lower(TG_OP),
                  'tenant_id', rec->>'tenant_id',
                  'id', rec->>'id',
                  'investigation_id', rec->>'investigation_id',
                  'recipient_user_id', rec->>'recipient_user_id'
                )::text
              );
              RETURN NULL;
            END $$
            """
        )
    )
    for table in NOTIFY_TABLES:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS opsmind_notify_change ON {table}"))
        op.execute(
            sa.text(
                f"CREATE TRIGGER opsmind_notify_change "
                f"AFTER INSERT OR UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION opsmind_notify_change()"
            )
        )


def downgrade() -> None:
    for table in NOTIFY_TABLES:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS opsmind_notify_change ON {table}"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS opsmind_notify_change()"))

    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE}"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"REVOKE USAGE, SELECT, UPDATE ON SEQUENCES FROM {APP_ROLE}"
        )
    )
    op.execute(sa.text(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}"))
    # Roles are cluster-wide: another database on the same server may still
    # grant to it, so dropping is best effort.
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              DROP ROLE IF EXISTS {APP_ROLE};
            EXCEPTION WHEN dependent_objects_still_exist THEN
              RAISE NOTICE 'Role {APP_ROLE} still referenced elsewhere; left in place';
            END $$
            """
        )
    )
