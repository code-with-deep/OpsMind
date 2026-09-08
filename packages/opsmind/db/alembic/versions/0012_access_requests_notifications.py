"""Add access_requests and notifications tables; extend users with status fields.

Revision ID: 0012_access_requests_notifications
Revises: 0011_remove_warehouse_connections
Create Date: 2026-09-08

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_access_requests_notifications"
down_revision: Union[str, None] = "0011_remove_warehouse_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend users table ────────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "users",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "revoked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_users_tenant_id_status",
        "users",
        ["tenant_id", "status"],
    )

    # ── access_requests ───────────────────────────────────────────────────────
    op.create_table(
        "access_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "invite_code_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invite_codes.id"),
            nullable=False,
        ),
        sa.Column("requester_email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.String(length=512), nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_access_requests_tenant_id_status",
        "access_requests",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_access_requests_tenant_id_created_at",
        "access_requests",
        ["tenant_id", "created_at"],
    )
    op.create_unique_constraint(
        "uq_access_requests_tenant_email",
        "access_requests",
        ["tenant_id", "requester_email"],
    )

    # Enable RLS on access_requests
    op.execute(sa.text("ALTER TABLE access_requests ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_select ON access_requests
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_modify ON access_requests
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "recipient_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "related_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("related_entity_type", sa.String(length=64), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notifications_recipient_is_read_created_at",
        "notifications",
        ["recipient_user_id", "is_read", "created_at"],
    )
    op.create_index(
        "ix_notifications_tenant_id_created_at",
        "notifications",
        ["tenant_id", "created_at"],
    )

    # Enable RLS on notifications
    op.execute(sa.text("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_select ON notifications
            FOR SELECT
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation_modify ON notifications
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )
    )


def downgrade() -> None:
    # notifications
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_modify ON notifications"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_select ON notifications"))
    op.drop_index("ix_notifications_tenant_id_created_at", table_name="notifications")
    op.drop_index("ix_notifications_recipient_is_read_created_at", table_name="notifications")
    op.drop_table("notifications")

    # access_requests
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_modify ON access_requests"))
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_select ON access_requests"))
    op.drop_constraint("uq_access_requests_tenant_email", "access_requests", type_="unique")
    op.drop_index("ix_access_requests_tenant_id_created_at", table_name="access_requests")
    op.drop_index("ix_access_requests_tenant_id_status", table_name="access_requests")
    op.drop_table("access_requests")

    # users columns
    op.drop_index("ix_users_tenant_id_status", table_name="users")
    op.drop_column("users", "revoked_by")
    op.drop_column("users", "revoked_at")
    op.drop_column("users", "status")
