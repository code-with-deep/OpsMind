"""P2-2: HNSW indexes on document_chunks.embedding and case_summaries.embedding.

Without these, every RAG/case-memory query is a full sequential scan over the
tenant's entire corpus — 5 RAG steps per investigation, each scanning all rows.

Revision ID: 0015_pgvector_hnsw_indexes
Revises: 0014_enforce_rls_and_harden_readonly
Create Date: 2026-09-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_pgvector_hnsw_indexes"
down_revision: Union[str, None] = "0014_enforce_rls_and_harden_readonly"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # HNSW index for cosine-distance search (matches the `<=>` operator used by
    # rag_tool.py and memory/persist.py's query_similar_cases()).
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_case_summaries_embedding_hnsw "
            "ON case_summaries USING hnsw (embedding vector_cosine_ops)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_case_summaries_embedding_hnsw"))
