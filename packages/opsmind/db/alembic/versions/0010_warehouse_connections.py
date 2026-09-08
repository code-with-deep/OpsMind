"""Add warehouse_connections for MT6 read-only connector.

Revision ID: 0010_warehouse_connections
Revises: 0009_ingest_jobs
Create Date: 2026-09-04

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_warehouse_connections"
down_revision: Union[str, None] = "0009_ingest_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "warehouse_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("dialect", sa.String(length=32), nullable=False, server_default="postgresql"),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="5432"),
        sa.Column("database", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("dsn_ciphertext", sa.Text(), nullable=False),
        sa.Column("schema_name", sa.String(length=64), nullable=False, server_default="public"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", name="uq_warehouse_connections_tenant"),
    )
    op.create_index("ix_warehouse_connections_tenant_id", "warehouse_connections", ["tenant_id"])
    op.create_index("ix_warehouse_connections_status", "warehouse_connections", ["status"])

    op.execute(sa.text("ALTER TABLE warehouse_connections ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_select ON warehouse_connections
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_modify ON warehouse_connections
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_modify ON warehouse_connections"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_select ON warehouse_connections"))
    op.drop_index("ix_warehouse_connections_status", table_name="warehouse_connections")
    op.drop_index("ix_warehouse_connections_tenant_id", table_name="warehouse_connections")
    op.drop_table("warehouse_connections")
