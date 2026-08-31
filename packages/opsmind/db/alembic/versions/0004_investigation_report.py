"""Add investigation report JSON fields for P3 graph runs.

Revision ID: 0004_investigation_report
Revises: 0003_memory_and_rag
Create Date: 2026-08-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_investigation_report"
down_revision: Union[str, None] = "0003_memory_and_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("plan", postgresql.JSONB(), nullable=True))
    op.add_column(
        "investigations", sa.Column("hypothesis", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "investigations", sa.Column("critique", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "investigations",
        sa.Column("recommendation", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "investigations",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("investigations", "retry_count")
    op.drop_column("investigations", "recommendation")
    op.drop_column("investigations", "critique")
    op.drop_column("investigations", "hypothesis")
    op.drop_column("investigations", "plan")
