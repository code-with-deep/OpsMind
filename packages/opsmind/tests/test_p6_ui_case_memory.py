"""P6 unit tests: Operator reviews, approval promotion to case memory, and history views."""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.db.memory_models import CaseSummary, Review
from opsmind.db.seed import DEMO_TENANT_ID
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.db.session import get_owner_session_factory
from opsmind.graph.runner import list_investigations_view, load_investigation_view, reset_graph_cache, run_investigation
from opsmind.memory.persist import create_investigation, list_case_summaries, query_similar_cases, record_review
from opsmind.tools.sql_tool import dispose_readonly_engine

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
READONLY_URL = os.getenv(
    "DATABASE_URL_READONLY",
    "postgresql+asyncpg://opsmind_readonly:opsmind_readonly@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"


def _db_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            inv = conn.execute(text("SELECT to_regclass('public.investigations')")).scalar()
            rev = conn.execute(text("SELECT to_regclass('public.reviews')")).scalar()
            cs = conn.execute(text("SELECT to_regclass('public.case_summaries')")).scalar()
        engine.dispose()
        return bool(inv) and bool(rev) and bool(cs)
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


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "OpsMind")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("DATABASE_URL_SYNC", SYNC_URL)
    monkeypatch.setenv("DATABASE_URL_READONLY", READONLY_URL)
    monkeypatch.setenv("DATABASE_URL", SYNC_URL)
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_API_BASE", "")
    monkeypatch.setenv("LLM_MODEL_FAST", "llama-3.1-8b-instant")
    monkeypatch.setenv("LLM_MODEL_STRONG", "llama-3.3-70b-versatile")
    monkeypatch.setenv("MAX_CRITIC_RETRIES", "2")
    monkeypatch.setenv("MAX_TOOL_CALLS_PER_RUN", "40")
    monkeypatch.setenv("OPSMIND_API_KEY", API_KEY)
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.mark.skipif(not _db_ready(), reason="Postgres with reviews + case_summaries tables required")
def test_reject_creates_review_without_case_summary():
    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        apply_tenant_session(session, DEMO_TENANT_ID)
        inv = create_investigation(
            session,
            tenant_id=DEMO_TENANT_ID,
            question="Why did warehouse pick time double?",
            status="completed",
        )
        inv_id = inv.id

        rev, case_summary = record_review(
            session,
            tenant_id=DEMO_TENANT_ID,
            investigation_id=inv_id,
            decision="rejected",
            reviewer="alice@opsmind.internal",
            notes="Recommendation did not address shift handovers.",
        )

        assert rev.id is not None
        assert rev.decision == "rejected"
        assert case_summary is None

        # Verify DB directly
        db_rev = session.get(Review, rev.id)
        assert db_rev is not None
        assert db_rev.reviewer == "alice@opsmind.internal"

        db_cs = session.query(CaseSummary).filter_by(investigation_id=inv_id).first()
        assert db_cs is None


@pytest.mark.skipif(not _db_ready(), reason="Postgres with reviews + case_summaries tables required")
def test_approve_creates_review_and_promotes_case_memory():
    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        apply_tenant_session(session, DEMO_TENANT_ID)
        inv = create_investigation(
            session,
            tenant_id=DEMO_TENANT_ID,
            question="Why did FastShip SLA drop in Midwest DC?",
            status="completed",
        )
        inv.hypothesis = {
            "summary": "Midwest DC weather storm led to carrier carrier backlogs.",
            "drivers": ["weather_delay", "carrier_sla_breach"],
        }
        inv.recommendation = {
            "summary": "Divert Midwest volume to South DC and notify customers.",
            "actions": ["Divert 30% volume to South DC", "Send proactive delay notices"],
            "confidence": 0.88,
        }
        inv.confidence = 0.88
        session.commit()
        inv_id = inv.id

        rev, case_summary = record_review(
            session,
            tenant_id=DEMO_TENANT_ID,
            investigation_id=inv_id,
            decision="approved",
            reviewer="lead_ops@opsmind.internal",
            notes="Confirmed effective playbook mitigation.",
        )

        assert rev.id is not None
        assert rev.decision == "approved"
        assert case_summary is not None
        assert case_summary.investigation_id == inv_id
        assert len(case_summary.embedding) == 384
        assert "carrier_sla_breach" in case_summary.drivers

        # Query similar cases
        matches = query_similar_cases(
            session,
            tenant_id=DEMO_TENANT_ID,
            query="FastShip Midwest carrier delays",
            top_k=20,
        )
        assert len(matches) >= 1
        top_ids = [m["investigation_id"] for m in matches]
        assert str(inv_id) in top_ids


@pytest.mark.skipif(not _db_ready(), reason="Postgres with reviews + case_summaries tables required")
def test_list_investigations_and_cases_api():
    client = TestClient(create_app())

    # Create investigation via API
    resp = client.post(
        "/investigations",
        headers={"X-API-Key": API_KEY},
        json={
            "question": "Why did revenue decrease last week compared to the prior week?",
            "wait": True,
        },
    )
    assert resp.status_code == 200
    inv_id = resp.json()["id"]

    # Submit review
    review_resp = client.post(
        f"/investigations/{inv_id}/reviews",
        headers={"X-API-Key": API_KEY},
        json={
            "decision": "approved",
            "reviewer": "test_lead",
            "notes": "Verified root cause.",
        },
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["case_promoted"] is True

    # List investigations
    list_resp = client.get(
        "/investigations",
        headers={"X-API-Key": API_KEY},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["investigations"]
    assert len(items) >= 1
    target = next((i for i in items if i["id"] == inv_id), None)
    assert target is not None
    assert target["is_approved"] is True
    assert target["latest_review_decision"] == "approved"

    # List cases memory
    cases_resp = client.get(
        "/investigations/cases/memory",
        headers={"X-API-Key": API_KEY},
    )
    assert cases_resp.status_code == 200
    cases = cases_resp.json()["cases"]
    assert len(cases) >= 1
    assert any(c["investigation_id"] == inv_id for c in cases)
