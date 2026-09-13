"""Move every serial id sequence past the highest id already in its table.

The seed script loads business rows with explicit ids and never advanced the
sequences. CSV ingest used to paper over that on every upload with
``setval(MAX(id))`` — which only worked while the app bypassed row-level
security. Now that tenant sessions run as ``opsmind_app`` (0016), MAX(id) only
sees the uploading tenant's rows, so a lagging sequence caused duplicate-key
errors on a new tenant's first upload. This one-off resync runs as the
migration role, which sees all rows.

Revision ID: 0017_resync_serial_sequences
Revises: 0016_app_role_and_realtime
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_resync_serial_sequences"
down_revision: Union[str, None] = "0016_app_role_and_realtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
              r record;
            BEGIN
              FOR r IN
                SELECT c.relname AS tbl,
                       a.attname AS col,
                       pg_get_serial_sequence(format('public.%I', c.relname), a.attname) AS seq
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND pg_get_serial_sequence(format('public.%I', c.relname), a.attname) IS NOT NULL
              LOOP
                -- Never lower a sequence: take the larger of its position and MAX(id).
                EXECUTE format(
                  'SELECT setval(%L, GREATEST((SELECT COALESCE(MAX(%I), 0) FROM public.%I), '
                  '(SELECT last_value FROM %s)) + 1, false)',
                  r.seq, r.col, r.tbl, r.seq
                );
              END LOOP;
            END $$
            """
        )
    )


def downgrade() -> None:
    # Advancing sequences is harmless and not meaningfully reversible.
    pass
