"""MT5 — product harden smoke: signup → invite → CSV → playbook → investigate → approve."""

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

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"


def _mt5_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            jobs = conn.execute(text("SELECT to_regclass('public.ingest_jobs')")).scalar()
            keys = conn.execute(text("SELECT to_regclass('public.api_keys')")).scalar()
        engine.dispose()
        return bool(jobs) and bool(keys)
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
    monkeypatch.setenv(
        "DATABASE_URL_READONLY",
        os.getenv(
            "DATABASE_URL_READONLY",
            "postgresql+asyncpg://opsmind_readonly:opsmind_readonly@localhost:5432/opsmind",
        ),
    )
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_API_BASE", "")
    monkeypatch.setenv("LLM_MODEL_FAST", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_STRONG", "gpt-4o")
    monkeypatch.setenv("MAX_CRITIC_RETRIES", "2")
    monkeypatch.setenv("MAX_TOOL_CALLS_PER_RUN", "40")
    monkeypatch.setenv("OPSMIND_API_KEY", API_KEY)
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-mt5-please-change")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "24")
    monkeypatch.setenv("OPSMIND_EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("AUTH_MAX_API_KEYS", "10")
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.mark.skipif(not _mt5_ready(), reason="MT4+ schema required")
def test_mt5_full_path_two_tenants() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    # --- Acme signup + rename ---
    acme = client.post(
        "/auth/signup",
        json={
            "company_name": f"Acme Hardened {suffix}",
            "email": f"acme-h-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert acme.status_code == 200, acme.text
    acme_token = acme.json()["access_token"]
    acme_tenant = acme.json()["user"]["tenant"]["id"]
    headers = {"Authorization": f"Bearer {acme_token}"}

    renamed = client.patch(
        "/auth/tenant",
        headers=headers,
        json={"name": f"Acme Renamed {suffix}"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["tenant"]["name"] == f"Acme Renamed {suffix}"

    # --- Invite investigator ---
    invite = client.post("/auth/invites", headers=headers, json={"max_uses": 2})
    assert invite.status_code == 200, invite.text
    code = invite.json()["invite"]["code"]

    join = client.post(
        "/auth/join",
        json={
            "invite_code": code,
            "email": f"inv-h-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert join.status_code == 200, join.text
    assert join.json()["user"]["tenant"]["id"] == acme_tenant
    assert join.json()["user"]["role"] == "investigator"

    # --- CSV + playbook ---
    up = client.post(
        "/data/csv",
        headers=headers,
        files={
            "file": (
                "acme.zip",
                io.BytesIO(sample_bundle_bytes()),
                "application/zip",
            )
        },
    )
    assert up.status_code == 200, up.text
    assert up.json()["ready"]["ready"] is True

    pb = client.post(
        "/playbooks",
        headers=headers,
        files={
            "file": (
                "sop.md",
                io.BytesIO(
                    f"# Acme SOP {suffix}\n\nEscalate stockouts using code ACME-{suffix}.\n".encode()
                ),
                "text/markdown",
            )
        },
    )
    assert pb.status_code == 200, pb.text

    # --- Investigate (may abstain without LLM; must not 409) ---
    inv = client.post(
        "/investigations",
        headers=headers,
        json={
            "question": "What was revenue on 2026-08-19?",
            "wait": True,
        },
    )
    assert inv.status_code == 200, inv.text
    body = inv.json()
    investigation_id = body["id"]
    audit = body.get("audit") or {}
    assert audit.get("tenant_id") == acme_tenant
    assert audit.get("user_id") == acme.json()["user"]["id"]

    # --- Approve → case memory ---
    review = client.post(
        f"/investigations/{investigation_id}/reviews",
        headers=headers,
        json={
            "decision": "approved",
            "reviewer": f"acme-h-{suffix}@example.com",
            "notes": "MT5 smoke approve",
        },
    )
    assert review.status_code == 200, review.text
    assert review.json().get("case_promoted") is True or review.json().get("review", {}).get(
        "decision"
    ) == "approved"

    cases = client.get("/investigations/cases/memory", headers=headers)
    assert cases.status_code == 200
    assert cases.json()["count"] >= 1

    # --- Beta tenant cannot see Acme investigations ---
    beta = client.post(
        "/auth/signup",
        json={
            "company_name": f"Beta Hardened {suffix}",
            "email": f"beta-h-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert beta.status_code == 200
    beta_headers = {"Authorization": f"Bearer {beta.json()['access_token']}"}
    beta_list = client.get("/investigations", headers=beta_headers)
    assert beta_list.status_code == 200
    assert all(i["id"] != investigation_id for i in beta_list.json()["investigations"])
    beta_cases = client.get("/investigations/cases/memory", headers=beta_headers)
    assert beta_cases.status_code == 200
    assert beta_cases.json()["count"] == 0
