"""MT1 — two-tenant isolation via API keys and scoped queries."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.auth import resolve_tenant_from_api_key
from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.auth.api_keys import hash_api_key, key_prefix
from opsmind.db.seed import DEMO_TENANT_ID
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_models import ApiKey, Tenant, TenantSettings
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.graph.runner import list_investigations_view
from opsmind.memory.persist import create_investigation

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"
BETA_KEY = "test-beta-tenant-key-0001"
BETA_TENANT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")


def _mt1_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            tenants = conn.execute(text("SELECT to_regclass('public.tenants')")).scalar()
            tenant_col = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'investigations' AND column_name = 'tenant_id'
                    """
                )
            ).scalar()
        engine.dispose()
        return bool(tenants) and bool(tenant_col)
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
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture()
def beta_tenant():
    if not _mt1_ready():
        pytest.skip("MT1 schema not applied — run alembic upgrade head")

    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        existing = session.get(Tenant, BETA_TENANT_ID)
        if existing is None:
            session.add(
                Tenant(
                    id=BETA_TENANT_ID,
                    name="Beta Corp",
                    slug="beta-test",
                    status="active",
                    domain_profile="ecommerce",
                )
            )
            session.add(
                TenantSettings(
                    tenant_id=BETA_TENANT_ID,
                    supported_domains=["revenue"],
                    enabled_sql_templates=[],
                )
            )
            session.add(
                ApiKey(
                    id=uuid.uuid4(),
                    tenant_id=BETA_TENANT_ID,
                    name="test",
                    key_hash=hash_api_key(BETA_KEY),
                    key_prefix=key_prefix(BETA_KEY),
                    scopes={},
                    created_by="test",
                )
            )
            session.commit()

        apply_tenant_session(session, BETA_TENANT_ID)
        create_investigation(
            session,
            tenant_id=BETA_TENANT_ID,
            question="Beta-only investigation for isolation test",
            status="completed",
        )
        session.commit()

    yield BETA_TENANT_ID

    # Leave beta tenant in place for repeat runs; investigations are tenant-scoped.


@pytest.mark.skipif(not _mt1_ready(), reason="MT1 migration required")
def test_api_key_resolves_distinct_tenants(beta_tenant) -> None:
    _ = beta_tenant
    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        demo_ctx = resolve_tenant_from_api_key(session, API_KEY)
        beta_ctx = resolve_tenant_from_api_key(session, BETA_KEY)

    assert demo_ctx.tenant_id == DEMO_TENANT_ID
    assert beta_ctx.tenant_id == BETA_TENANT_ID
    assert demo_ctx.tenant_id != beta_ctx.tenant_id


@pytest.mark.skipif(not _mt1_ready(), reason="MT1 migration required")
def test_list_investigations_isolated_per_tenant(beta_tenant) -> None:
    _ = beta_tenant
    factory = get_owner_session_factory(SYNC_URL)

    with factory() as session:
        apply_tenant_session(session, DEMO_TENANT_ID)
        demo_items = list_investigations_view(session, tenant_id=DEMO_TENANT_ID, limit=100)

    with factory() as session:
        apply_tenant_session(session, BETA_TENANT_ID)
        beta_items = list_investigations_view(session, tenant_id=BETA_TENANT_ID, limit=100)

    demo_questions = {item["question"] for item in demo_items}
    beta_questions = {item["question"] for item in beta_items}

    assert "Beta-only investigation for isolation test" in beta_questions
    assert "Beta-only investigation for isolation test" not in demo_questions


@pytest.mark.skipif(not _mt1_ready(), reason="MT1 migration required")
def test_api_list_respects_tenant_key(beta_tenant) -> None:
    _ = beta_tenant
    client = TestClient(create_app())

    demo_resp = client.get("/investigations", headers={"X-API-Key": API_KEY})
    beta_resp = client.get("/investigations", headers={"X-API-Key": BETA_KEY})

    assert demo_resp.status_code == 200
    assert beta_resp.status_code == 200

    demo_questions = {i["question"] for i in demo_resp.json()["investigations"]}
    beta_questions = {i["question"] for i in beta_resp.json()["investigations"]}

    assert "Beta-only investigation for isolation test" in beta_questions
    assert "Beta-only investigation for isolation test" not in demo_questions
