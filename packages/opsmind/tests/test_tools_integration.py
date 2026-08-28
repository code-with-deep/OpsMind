"""Integration tests against local Docker Postgres (skip if unavailable)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from opsmind.db.memory_models import Finding, ToolInvocation
from opsmind.grounding.registry import SourceIdRegistry
from opsmind.tools.rag_tool import run_rag_tool
from opsmind.tools.sql_tool import SqlToolError, dispose_readonly_engine, run_sql_tool

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
READONLY_URL = os.getenv(
    "DATABASE_URL_READONLY",
    "postgresql+asyncpg://opsmind_readonly:opsmind_readonly@localhost:5432/opsmind",
)


def _db_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            # P2 migration present?
            row = conn.execute(
                text("SELECT to_regclass('public.tool_invocations')")
            ).scalar()
            docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        engine.dispose()
        return bool(row) and int(docs or 0) >= 5
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="Postgres with P2 schema + ingested playbooks not available",
)


@pytest.fixture()
def owner_session() -> Session:
    dispose_readonly_engine()
    engine = create_engine(SYNC_URL, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        dispose_readonly_engine()


def test_sql_tool_persists_invocation_and_finding(owner_session: Session):
    registry = SourceIdRegistry()
    result = run_sql_tool(
        template_key="revenue_week_totals",
        params={"start_date": "2026-08-17", "end_date": "2026-08-23"},
        database_url_readonly=READONLY_URL,
        owner_session=owner_session,
        registry=registry,
    )
    assert result.rows
    assert result.source_id.startswith("sql_")
    assert registry.exists(result.source_id)
    assert result.tool_invocation_id
    assert result.finding_id

    inv = owner_session.get(ToolInvocation, uuid.UUID(result.tool_invocation_id))
    finding = owner_session.get(Finding, uuid.UUID(result.finding_id))
    assert inv is not None
    assert finding is not None
    assert finding.source_id == result.source_id
    assert "claim" in finding.claim.lower() or finding.claim


def test_sql_unknown_template_does_not_execute(owner_session: Session):
    before = owner_session.scalars(select(ToolInvocation)).all()
    before_count = len(before)
    with pytest.raises(SqlToolError, match="Unknown SQL template"):
        run_sql_tool(
            template_key="not_a_real_template",
            params={},
            database_url_readonly=READONLY_URL,
            owner_session=owner_session,
        )
    after_count = len(owner_session.scalars(select(ToolInvocation)).all())
    assert after_count == before_count


def test_rag_stockout_escalation_top_hit(owner_session: Session):
    result = run_rag_tool(
        query="stockout escalation for top seller inventory",
        owner_session=owner_session,
        min_score=0.01,
    )
    assert result.hits, "expected at least one playbook hit"
    top = result.hits[0]
    assert top.doc_key == "stockout-escalation"
    assert top.score > 0.05
    assert result.tool_invocation_id
    assert result.finding_id
