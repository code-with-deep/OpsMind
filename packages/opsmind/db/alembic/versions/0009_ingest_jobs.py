"""Add ingest_jobs table for MT4 CSV data plane.

Revision ID: 0009_ingest_jobs
Revises: 0008_invite_codes
Create Date: 2026-09-04

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_ingest_jobs"
down_revision: Union[str, None] = "0008_invite_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="csv"),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "row_counts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingest_jobs_tenant_id", "ingest_jobs", ["tenant_id"])
    op.create_index("ix_ingest_jobs_status", "ingest_jobs", ["status"])

    op.execute(sa.text("ALTER TABLE ingest_jobs ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_select ON ingest_jobs
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_modify ON ingest_jobs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_modify ON ingest_jobs"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_select ON ingest_jobs"))
    op.drop_index("ix_ingest_jobs_status", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_tenant_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")
