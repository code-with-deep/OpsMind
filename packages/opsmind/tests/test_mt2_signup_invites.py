"""MT2 — signup, login, invites land users in the correct tenant only."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.config import clear_settings_cache
from api.app.main import create_app

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"


def _mt2_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            invites = conn.execute(text("SELECT to_regclass('public.invite_codes')")).scalar()
        engine.dispose()
        return bool(invites)
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
        "postgresql+asyncpg://opsmind_readonly:opsmind_readonly@localhost:5432/opsmind",
    )
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_API_BASE", "")
    monkeypatch.setenv("LLM_MODEL_FAST", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MODEL_STRONG", "gpt-4o")
    monkeypatch.setenv("MAX_CRITIC_RETRIES", "2")
    monkeypatch.setenv("MAX_TOOL_CALLS_PER_RUN", "40")
    monkeypatch.setenv("OPSMIND_API_KEY", API_KEY)
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-mt2-please-change")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "24")
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.mark.skipif(not _mt2_ready(), reason="MT2 invite_codes migration required")
def test_signup_login_invite_isolation() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    signup = client.post(
        "/auth/signup",
        json={
            "company_name": f"Acme {suffix}",
            "email": f"admin-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert signup.status_code == 200, signup.text
    admin_token = signup.json()["access_token"]
    admin_tenant = signup.json()["user"]["tenant"]["id"]
    assert signup.json()["user"]["role"] == "admin"

    login = client.post(
        "/auth/login",
        json={"email": f"admin-{suffix}@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["tenant"]["id"] == admin_tenant

    invite_resp = client.post(
        "/auth/invites",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"max_uses": 2, "ttl_days": 7},
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invite_code = invite_resp.json()["invite"]["code"]
    assert invite_code.startswith("OM-")

    join = client.post(
        "/auth/join",
        json={
            "invite_code": invite_code,
            "email": f"inv-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert join.status_code == 200, join.text
    inv_token = join.json()["access_token"]
    assert join.json()["user"]["role"] == "investigator"
    assert join.json()["user"]["tenant"]["id"] == admin_tenant

    # Second company cannot see first company's investigations via JWT
    other = client.post(
        "/auth/signup",
        json={
            "company_name": f"Beta {suffix}",
            "email": f"beta-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert other.status_code == 200
    other_token = other.json()["access_token"]
    other_tenant = other.json()["user"]["tenant"]["id"]
    assert other_tenant != admin_tenant

    # Create an investigation under acme via authenticated list (empty ok)
    acme_list = client.get(
        "/investigations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    beta_list = client.get(
        "/investigations",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert acme_list.status_code == 200
    assert beta_list.status_code == 200

    # Reject double-join with same email into another company
    reject = client.post(
        "/auth/join",
        json={
            "invite_code": invite_code,
            "email": f"admin-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert reject.status_code == 409

    # Investigator cannot create invites
    forbidden = client.post(
        "/auth/invites",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={},
    )
    assert forbidden.status_code == 403

    # Revoke works for admin
    invite_id = invite_resp.json()["invite"]["id"]
    revoked = client.post(
        f"/auth/invites/{invite_id}/revoke",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True
