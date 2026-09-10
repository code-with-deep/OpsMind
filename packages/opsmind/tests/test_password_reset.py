"""Password change + email reset flows."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.auth.password_reset import (
    generate_reset_token,
    hash_reset_token,
    reset_token_prefix,
)
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_models import PasswordResetToken, User

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"


def _ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            table = conn.execute(
                text("SELECT to_regclass('public.password_reset_tokens')")
            ).scalar()
        engine.dispose()
        return bool(table)
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
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-password-reset")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "24")
    monkeypatch.setenv("APP_PUBLIC_URL", "http://localhost:3000")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("AUTH_PASSWORD_RESET_TTL_MINUTES", "60")
    monkeypatch.setenv("AUTH_PASSWORD_RESET_MAX_PER_HOUR", "5")
    clear_settings_cache()
    yield
    clear_settings_cache()


def _signup(client: TestClient, suffix: str, password: str = "password123"):
    res = client.post(
        "/auth/signup",
        json={
            "company_name": f"ResetCo {suffix}",
            "email": f"admin-{suffix}@example.com",
            "password": password,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.skipif(not _ready(), reason="0013_password_reset migration required")
def test_change_password_and_invalidate_old_jwt() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    data = _signup(client, suffix)
    old_token = data["access_token"]

    bad = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={"current_password": "wrong-password", "new_password": "newpass123"},
    )
    assert bad.status_code == 401

    changed = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={"current_password": "password123", "new_password": "newpass123"},
    )
    assert changed.status_code == 200, changed.text
    new_token = changed.json()["access_token"]
    assert new_token != old_token

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200

    stale = client.get("/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert stale.status_code == 401

    login = client.post(
        "/auth/login",
        json={"email": f"admin-{suffix}@example.com", "password": "newpass123"},
    )
    assert login.status_code == 200


@pytest.mark.skipif(not _ready(), reason="0013_password_reset migration required")
def test_forgot_reset_password_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    _signup(client, suffix, password="password123")
    email = f"admin-{suffix}@example.com"

    unknown = client.post(
        "/auth/forgot-password",
        json={"email": f"missing-{suffix}@example.com"},
    )
    assert unknown.status_code == 200
    assert "If an account exists" in unknown.json()["message"]

    fixed_raw = "test-reset-token-" + suffix + "-abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setattr(
        "api.app.routes.auth.generate_reset_token",
        lambda: fixed_raw,
    )

    forgot = client.post("/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    assert forgot.json()["message"] == unknown.json()["message"]

    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        row = session.scalars(
            select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc())
        ).first()
        assert row is not None
        assert row.token_hash == hash_reset_token(fixed_raw)
        assert row.used_at is None

    reset = client.post(
        "/auth/reset-password",
        json={"token": fixed_raw, "new_password": "resetpass99"},
    )
    assert reset.status_code == 200, reset.text

    again = client.post(
        "/auth/reset-password",
        json={"token": fixed_raw, "new_password": "anotherpass1"},
    )
    assert again.status_code == 400

    old_login = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login",
        json={"email": email, "password": "resetpass99"},
    )
    assert new_login.status_code == 200


@pytest.mark.skipif(not _ready(), reason="0013_password_reset migration required")
def test_expired_reset_token_rejected() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    data = _signup(client, suffix)
    email = data["user"]["email"]

    factory = get_owner_session_factory(SYNC_URL)
    raw = generate_reset_token()
    with factory() as session:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None
        session.add(
            PasswordResetToken(
                id=uuid.uuid4(),
                tenant_id=user.tenant_id,
                user_id=user.id,
                token_hash=hash_reset_token(raw),
                token_prefix=reset_token_prefix(raw),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        session.commit()

    expired = client.post(
        "/auth/reset-password",
        json={"token": raw, "new_password": "newpassword1"},
    )
    assert expired.status_code == 400
