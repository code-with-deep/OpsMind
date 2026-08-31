"""Add audit JSONB column for P5 terminal audit completeness.

Revision ID: 0005_investigation_audit
Revises: 0004_investigation_report
Create Date: 2026-08-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_investigation_audit"
down_revision: Union[str, None] = "0004_investigation_report"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("audit", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("investigations", "audit")
