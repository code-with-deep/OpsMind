"""MT6 — warehouse connector: encrypt, verify, fail-closed, ready-gate."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.auth.secrets import decrypt_secret, encrypt_secret
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.db.warehouse import resolve_sql_target
from opsmind.tools.sql_tool import SqlToolError, execute_sql_query_readonly

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


def _pg_host_from_url(url: str) -> str:
    """Host reachable from the pytest process (localhost on host, db in Compose)."""
    # postgresql://user:pass@host:port/db
    after_at = url.split("@", 1)[-1]
    return after_at.split(":", 1)[0].split("/", 1)[0] or "localhost"


WH_HOST = _pg_host_from_url(SYNC_URL)


def _mt6_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            wh = conn.execute(text("SELECT to_regclass('public.warehouse_connections')")).scalar()
        engine.dispose()
        return bool(wh)
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
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-mt6-please-change")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "24")
    monkeypatch.setenv("OPSMIND_EMBEDDING_PROVIDER", "local")
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_secret_roundtrip() -> None:
    token = encrypt_secret("postgresql://u:p@h:5432/db")
    assert decrypt_secret(token).startswith("postgresql://")


@pytest.mark.skipif(not _mt6_ready(), reason="MT6 warehouse_connections migration required")
def test_warehouse_verify_fail_closed_and_ready() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    signup = client.post(
        "/auth/signup",
        json={
            "company_name": f"Wh Corp {suffix}",
            "email": f"wh-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert signup.status_code == 200, signup.text
    token = signup.json()["access_token"]
    tenant_id = uuid.UUID(signup.json()["user"]["tenant"]["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # Not ready without CSV or warehouse
    ready0 = client.get("/data/ready", headers=headers)
    assert ready0.json()["ready"] is False

    # Bad password → failed status, secrets not returned
    bad = client.put(
        "/warehouse",
        headers=headers,
        json={
            "host": WH_HOST,
            "port": 5432,
            "database": "opsmind",
            "username": "opsmind_readonly",
            "password": "wrong-password",
            "schema_name": "public",
        },
    )
    assert bad.status_code == 400, bad.text
    detail = bad.json()["detail"]
    assert detail["connection"]["status"] == "failed"
    assert "password" not in detail["connection"]
    assert "dsn" not in str(detail).lower()

    # Fail closed: unresolved verified required when row exists but failed
    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        with pytest.raises(ValueError, match="not verified"):
            resolve_sql_target(
                session,
                tenant_id=tenant_id,
                fallback_database_url_readonly=READONLY_SYNC,
            )

    # Investigator cannot save
    invite = client.post("/auth/invites", headers=headers, json={})
    code = invite.json()["invite"]["code"]
    join = client.post(
        "/auth/join",
        json={
            "invite_code": code,
            "email": f"wh-inv-{suffix}@example.com",
            "password": "password123",
        },
    )
    inv_headers = {"Authorization": f"Bearer {join.json()['access_token']}"}
    denied = client.put(
        "/warehouse",
        headers=inv_headers,
        json={
            "host": WH_HOST,
            "port": 5432,
            "database": "opsmind",
            "username": "opsmind_readonly",
            "password": "opsmind_readonly",
            "schema_name": "public",
        },
    )
    assert denied.status_code == 403

    # Correct readonly user → verified (shared demo schema exists)
    ok = client.put(
        "/warehouse",
        headers=headers,
        json={
            "host": WH_HOST,
            "port": 5432,
            "database": "opsmind",
            "username": "opsmind_readonly",
            "password": "opsmind_readonly",
            "schema_name": "public",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["connection"]["status"] == "verified"
    assert "password" not in ok.json()["connection"]

    ready1 = client.get("/data/ready", headers=headers)
    assert ready1.json()["ready"] is True
    assert ready1.json()["warehouse_ready"] is True

    # SQL via warehouse engine — allowlisted templates + tenant GUC when RLS applies.
    with factory() as session:
        apply_tenant_session(session, tenant_id)
        rows = execute_sql_query_readonly(
            "revenue_by_day",
            {"start_date": "2026-08-01", "end_date": "2026-08-31"},
            READONLY_SYNC,
            tenant_id,
            owner_session=session,
        )
        assert isinstance(rows, list)

    # Delete connector
    deleted = client.delete("/warehouse", headers=headers)
    assert deleted.status_code == 200
    ready2 = client.get("/data/ready", headers=headers)
    assert ready2.json()["warehouse_ready"] is False
