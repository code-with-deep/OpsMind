"""Empty baseline migration — schema models arrive in P1.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-27

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty in P0. P1 adds business tables.
    pass


def downgrade() -> None:
    pass
