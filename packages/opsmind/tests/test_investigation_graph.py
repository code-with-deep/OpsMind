"""P3 investigation graph integration tests (heuristic path; no LLM key required)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from opsmind.db.seed import DEMO_TENANT_ID
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.graph.runner import (
    load_investigation_view,
    reset_graph_cache,
    run_investigation,
)
from opsmind.tools.sql_tool import dispose_readonly_engine

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
            inv = conn.execute(text("SELECT to_regclass('public.investigations')")).scalar()
            plan_col = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='investigations' AND column_name='recommendation'"
                )
            ).scalar()
            docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        engine.dispose()
        return bool(inv) and bool(plan_col) and int(docs or 0) >= 1
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="Postgres with P3 schema + playbooks not available",
)


@pytest.fixture()
def settings():
    reset_graph_cache()
    dispose_readonly_engine()
    return SimpleNamespace(
        database_url_sync=SYNC_URL,
        database_url_readonly=READONLY_URL,
        llm_api_key="",  # force heuristic agents
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model_fast="llama-3.1-8b-instant",
        llm_model_strong="llama-3.3-70b-versatile",
        max_critic_retries=2,
        max_tool_calls_per_run=40,
    )


def test_happy_path_revenue_drop_investigation(settings):
    question = (
        "Why did our revenue decrease this week (2026-08-17 to 2026-08-23), "
        "and what should we do?"
    )
    result = run_investigation(
        question=question,
        settings=settings,
        tenant_id=DEMO_TENANT_ID,
        use_postgres_checkpoint=False,
    )
    assert result["status"] == "completed"
    assert result["recommendation"]
    assert result["recommendation"]["actions"]
    assert result["finding_count"] >= 2

    trace = result["node_trace"]
    for node in (
        "planner",
        "data_investigator",
        "knowledge",
        "synthesizer",
        "critic",
        "recommender",
    ):
        assert node in trace

    engine = create_engine(SYNC_URL, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        apply_tenant_session(session, DEMO_TENANT_ID)
        view = load_investigation_view(
            session,
            __import__("uuid").UUID(result["investigation_id"]),
            tenant_id=DEMO_TENANT_ID,
        )
    engine.dispose()

    assert view["status"] == "completed"
    assert view["recommendation"] is not None
    event_types = [e["event_type"] for e in view["timeline"]]
    assert "agent_planner" in event_types
    assert "agent_recommender" in event_types
    assert "graph_completed" in event_types
    assert len(view["findings"]) >= 1
