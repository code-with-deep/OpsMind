"""P4 unit + integration tests: triage, verifier, retry, abstain paths."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from opsmind.agents.critic import score_critique
from opsmind.agents.triage import classify_question
from opsmind.graph.runner import reset_graph_cache, run_investigation
from opsmind.grounding.verifier import verify_claim_source_map
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
            docs = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        engine.dispose()
        return bool(inv) and int(docs or 0) >= 1
    except Exception:
        return False


@pytest.fixture()
def settings():
    reset_graph_cache()
    dispose_readonly_engine()
    return SimpleNamespace(
        database_url_sync=SYNC_URL,
        database_url_readonly=READONLY_URL,
        llm_api_key="",
        llm_api_base="https://api.groq.com/openai/v1",
        llm_model_fast="llama-3.1-8b-instant",
        llm_model_strong="llama-3.3-70b-versatile",
        max_critic_retries=2,
        max_tool_calls_per_run=40,
    )


def test_triage_poem_unsupported():
    route, _ = classify_question("write a poem about warehouses")
    assert route == "unsupported"


def test_triage_payroll_unsupported():
    route, reason = classify_question("How much payroll overtime did warehouse staff work?")
    assert route == "unsupported"
    assert "outside" in reason.lower() or "catalog" in reason.lower() or "domain" in reason.lower()


def test_triage_vague_needs_clarification():
    route, _ = classify_question("why are things bad?")
    assert route == "needs_clarification"


def test_citation_verifier_rejects_fake_source_id():
    result = verify_claim_source_map(
        [{"claim": "Revenue dropped 60%", "source_ids": ["sql_fake_does_not_exist"]}],
        valid_source_ids={"sql_real_abc"},
    )
    assert result.ok is False
    assert result.unknown_source_ids


def test_citation_verifier_accepts_real_source_id():
    result = verify_claim_source_map(
        [{"claim": "Revenue dropped", "source_ids": ["sql_real_abc"]}],
        valid_source_ids={"sql_real_abc"},
    )
    assert result.ok is True


def test_critic_retries_when_sql_missing():
    critique = score_critique(
        findings=[{"kind": "rag", "purpose": "playbook", "evidence": {"claim": "sop"}}],
        hypothesis={"summary": "x", "gaps": []},
        retry_count=0,
        max_retries=2,
        question="Why did revenue decrease?",
    )
    assert critique.decision == "retry"
    assert "missing_sql_evidence" in critique.gaps


def test_critic_fail_soft_after_max_retries():
    critique = score_critique(
        findings=[],
        hypothesis={"summary": "x", "gaps": []},
        retry_count=2,
        max_retries=2,
        question="Why did revenue decrease?",
    )
    assert critique.decision == "fail_soft"


@pytest.mark.skipif(not _db_ready(), reason="Postgres + playbooks not available")
def test_e2e_poem_unsupported(settings):
    result = run_investigation(
        question="write a poem about warehouses",
        settings=settings,
        use_postgres_checkpoint=False,
    )
    assert result["status"] == "unsupported"
    assert "data_investigator" not in (result.get("node_trace") or [])


@pytest.mark.skipif(not _db_ready(), reason="Postgres + playbooks not available")
def test_e2e_payroll_unsupported(settings):
    result = run_investigation(
        question="Explain payroll overtime costs for warehouse associates",
        settings=settings,
        use_postgres_checkpoint=False,
    )
    assert result["status"] == "unsupported"
    domains = (result.get("recommendation") or {}).get("supported_domains") or []
    assert domains


@pytest.mark.skipif(not _db_ready(), reason="Postgres + playbooks not available")
def test_e2e_vague_needs_clarification(settings):
    result = run_investigation(
        question="why are things bad?",
        settings=settings,
        use_postgres_checkpoint=False,
    )
    assert result["status"] == "needs_clarification"


@pytest.mark.skipif(not _db_ready(), reason="Postgres + playbooks not available")
def test_e2e_critic_retry_when_sql_blocked_first_pass(settings):
    result = run_investigation(
        question=(
            "Why did our revenue decrease this week (2026-08-17 to 2026-08-23), "
            "and what should we do?"
        ),
        settings=settings,
        use_postgres_checkpoint=False,
        runtime_overrides={"block_sql_on_first_pass": True},
    )
    assert result["retry_count"] >= 1
    assert "critic" in (result.get("node_trace") or [])
    # After retry, SQL is allowed → should complete (or at least leave retry path).
    assert result["status"] in {"completed", "insufficient_evidence"}
    if result["status"] == "completed":
        assert result["recommendation"]
        assert result["finding_count"] >= 1
