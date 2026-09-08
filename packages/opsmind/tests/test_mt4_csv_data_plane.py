"""MT4 — CSV ingest isolation + investigation ready-gate."""

from __future__ import annotations

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.db.ingest_csv import sample_bundle_bytes
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.tools.sql_tool import execute_sql_query_readonly

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
READONLY_URL = os.getenv(
    "DATABASE_URL_READONLY",
    "postgresql+asyncpg://opsmind_readonly:opsmind_readonly@localhost:5432/opsmind",
)
READONLY_SYNC = READONLY_URL.replace("postgresql+asyncpg://", "postgresql://")
API_KEY = "test-opsmind-api-key"


def _mt4_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            jobs = conn.execute(text("SELECT to_regclass('public.ingest_jobs')")).scalar()
        engine.dispose()
        return bool(jobs)
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "OpsMind")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("DATABASE_URL_SYNC", SYNC_URL)
    monkeypatch.setenv("DATABASE_URL", SYNC_URL)
    monkeypatch.setenv("DATABASE_URL_READONLY", READONLY_URL)
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_API_BASE", "")
    monkeypatch.setenv("LLM_MODEL_FAST", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_STRONG", "gpt-4o")
    monkeypatch.setenv("MAX_CRITIC_RETRIES", "2")
    monkeypatch.setenv("MAX_TOOL_CALLS_PER_RUN", "40")
    monkeypatch.setenv("OPSMIND_API_KEY", API_KEY)
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-mt4-please-change")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "24")
    monkeypatch.setenv("OPSMIND_EMBEDDING_PROVIDER", "local")
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.mark.skipif(not _mt4_ready(), reason="MT4 ingest_jobs migration required")
def test_csv_ready_gate_and_tenant_isolation() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    acme = client.post(
        "/auth/signup",
        json={
            "company_name": f"Acme Data {suffix}",
            "email": f"acme-data-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert acme.status_code == 200, acme.text
    acme_token = acme.json()["access_token"]
    acme_tenant = uuid.UUID(acme.json()["user"]["tenant"]["id"])

    beta = client.post(
        "/auth/signup",
        json={
            "company_name": f"Beta Data {suffix}",
            "email": f"beta-data-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert beta.status_code == 200, beta.text
    beta_token = beta.json()["access_token"]
    beta_tenant = uuid.UUID(beta.json()["user"]["tenant"]["id"])

    # Ready-gate: no CSV yet → 409
    blocked = client.post(
        "/investigations",
        headers={"Authorization": f"Bearer {acme_token}"},
        json={"question": "Why did revenue drop last week?", "wait": True},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["error"] == "tenant_data_not_ready"

    ready_before = client.get(
        "/data/ready",
        headers={"Authorization": f"Bearer {acme_token}"},
    )
    assert ready_before.status_code == 200
    assert ready_before.json()["ready"] is False

    bundle = sample_bundle_bytes()
    up = client.post(
        "/data/csv",
        headers={"Authorization": f"Bearer {acme_token}"},
        files={"file": ("acme-data.zip", io.BytesIO(bundle), "application/zip")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["job"]["status"] == "done"
    assert up.json()["ready"]["ready"] is True
    assert up.json()["job"]["row_counts"]["orders"] == 4

    ready_after = client.get(
        "/data/ready",
        headers={"Authorization": f"Bearer {acme_token}"},
    )
    assert ready_after.json()["ready"] is True

    # Beta still blocked / not ready
    beta_ready = client.get(
        "/data/ready",
        headers={"Authorization": f"Bearer {beta_token}"},
    )
    assert beta_ready.json()["ready"] is False

    # Metrics isolation: Acme revenue for 2026-08-19 should be 50.00 from sample
    rows = execute_sql_query_readonly(
        "revenue_by_day",
        {"start_date": "2026-08-19", "end_date": "2026-08-19"},
        READONLY_SYNC,
        tenant_id=acme_tenant,
    )
    assert rows, "Acme should see its own daily_metrics"
    assert float(rows[0]["revenue"]) == 50.0

    beta_rows = execute_sql_query_readonly(
        "revenue_by_day",
        {"start_date": "2026-08-19", "end_date": "2026-08-19"},
        READONLY_SYNC,
        tenant_id=beta_tenant,
    )
    assert beta_rows == []

    # Re-upload replace for Acme still works
    up2 = client.post(
        "/data/csv",
        headers={"Authorization": f"Bearer {acme_token}"},
        files={"file": ("acme-data.zip", io.BytesIO(bundle), "application/zip")},
    )
    assert up2.status_code == 200, up2.text

    jobs = client.get(
        "/data/ingest-jobs",
        headers={"Authorization": f"Bearer {acme_token}"},
    )
    assert jobs.status_code == 200
    assert jobs.json()["count"] >= 2
