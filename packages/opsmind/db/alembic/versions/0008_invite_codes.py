"""Add invite_codes table for MT2 signup/invites.

Revision ID: 0008_invite_codes
Revises: 0007_multi_tenant_core
Create Date: 2026-09-04

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_invite_codes"
down_revision: Union[str, None] = "0007_multi_tenant_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_prefix", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code_hash", name="uq_invite_codes_code_hash"),
    )
    op.create_index("ix_invite_codes_tenant_id", "invite_codes", ["tenant_id"])
    op.create_index("ix_invite_codes_code_hash", "invite_codes", ["code_hash"])


def downgrade() -> None:
    op.drop_index("ix_invite_codes_code_hash", table_name="invite_codes")
    op.drop_index("ix_invite_codes_tenant_id", table_name="invite_codes")
    op.drop_table("invite_codes")
