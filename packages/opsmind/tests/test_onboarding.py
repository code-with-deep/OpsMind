"""Onboarding: get-started status, one-click sample store, data-based suggestions."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.agents.triage import classify_question

SYNC_URL = os.getenv("DATABASE_URL_SYNC", "postgresql://opsmind:opsmind@localhost:5432/opsmind")
READONLY_URL = os.getenv(
    "DATABASE_URL_READONLY",
    "postgresql+asyncpg://opsmind_readonly:opsmind_readonly@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"


def _db_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            ready = conn.execute(text("SELECT to_regclass('public.ingest_jobs') IS NOT NULL")).scalar()
        engine.dispose()
        return bool(ready)
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="Postgres with the OpsMind schema required")


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "OpsMind")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("DATABASE_URL_SYNC", SYNC_URL)
    monkeypatch.setenv("DATABASE_URL", SYNC_URL)
    monkeypatch.setenv("DATABASE_URL_READONLY", READONLY_URL)
    # Deterministic agents: never call a real LLM from tests, whatever .env holds.
    for key in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "LLM_API_KEY"):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("MAX_CRITIC_RETRIES", "2")
    monkeypatch.setenv("MAX_TOOL_CALLS_PER_RUN", "40")
    monkeypatch.setenv("OPSMIND_API_KEY", API_KEY)
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-onboarding-please-change")
    monkeypatch.setenv("OPSMIND_EMBEDDING_PROVIDER", "local")
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_new_workspace_gets_started_with_the_sample_store() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    signup = client.post(
        "/auth/signup",
        json={
            "company_name": f"Onboarding {suffix}",
            "email": f"onboarding-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert signup.status_code == 200, signup.text
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    fresh = client.get("/onboarding/status", headers=headers).json()
    assert fresh["is_admin"] is True
    assert fresh["ready_to_investigate"] is False
    assert fresh["missing"] == ["business_data", "playbooks"]
    assert fresh["data_coverage"] is None
    assert fresh["suggested_questions"] == []
    assert fresh["sample_data_available"] is True

    loaded = client.post("/onboarding/sample-data", headers=headers)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["loaded"] == {"business_data": True, "playbooks": 5}
    assert loaded.json()["ready_to_investigate"] is True

    status = client.get("/onboarding/status", headers=headers).json()
    assert status["ready_to_investigate"] is True
    assert status["missing"] == []
    assert status["steps"]["business_data"]["orders"] > 0
    assert status["steps"]["playbooks"]["count"] == 5
    coverage = status["data_coverage"]
    assert coverage is not None and coverage["start"] <= coverage["end"]

    suggestions = status["suggested_questions"]
    assert [s["kind"] for s in suggestions][:1] == ["revenue"]
    assert len(suggestions) >= 3
    for suggestion in suggestions:
        route, reason = classify_question(suggestion["question"])
        assert route not in {"unsupported", "needs_clarification"}, (suggestion["question"], reason)

    again = client.post("/onboarding/sample-data", headers=headers)
    assert again.status_code == 200, again.text
    assert again.json()["loaded"] == {"business_data": False, "playbooks": 0}

    run = client.post(
        "/investigations", headers=headers, json={"question": suggestions[0]["question"], "wait": True}
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "completed"

    after = client.get("/onboarding/status", headers=headers).json()
    assert after["steps"]["first_investigation"] == {
        "done": True,
        "count": 1,
        "latest_id": run.json()["id"],
    }
    assert after["steps"]["first_review"]["done"] is False


def test_loading_sample_data_requires_an_admin() -> None:
    client = TestClient(create_app())
    response = client.post("/onboarding/sample-data", headers={"X-API-Key": API_KEY})
    assert response.status_code == 403, response.text
