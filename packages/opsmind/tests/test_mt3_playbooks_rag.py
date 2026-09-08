"""MT3 — per-tenant playbook upload + RAG isolation (Acme never sees Beta)."""

from __future__ import annotations

import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.app.config import clear_settings_cache
from api.app.main import create_app
from opsmind.db.ingest_playbooks import approx_token_count, chunk_markdown
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.tools.rag_tool import retrieve_playbooks

SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://opsmind:opsmind@localhost:5432/opsmind",
)
API_KEY = "test-opsmind-api-key"


def _mt3_ready() -> bool:
    try:
        engine = create_engine(SYNC_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            docs = conn.execute(text("SELECT to_regclass('public.documents')")).scalar()
            tenants = conn.execute(text("SELECT to_regclass('public.tenants')")).scalar()
            tenant_col = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'documents' AND column_name = 'tenant_id'
                    """
                )
            ).scalar()
        engine.dispose()
        return bool(docs) and bool(tenants) and bool(tenant_col)
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
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-mt3-please-change")
    monkeypatch.setenv("JWT_EXPIRE_HOURS", "24")
    monkeypatch.setenv("OPSMIND_EMBEDDING_PROVIDER", "local")
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_chunk_markdown_heading_aware_with_overlap() -> None:
    sections = []
    for i in range(8):
        body = " ".join([f"word{i}_{j}" for j in range(200)])
        sections.append(f"## Section {i}\n\n{body}")
    content = "# Playbook\n\n" + "\n\n".join(sections)
    chunks = chunk_markdown(content)
    assert len(chunks) >= 2
    for chunk in chunks:
        # Hard upper bound with a small slack for packing edge cases.
        assert approx_token_count(chunk) <= 768 * 1.5


@pytest.mark.skipif(not _mt3_ready(), reason="MT1+ documents tenant schema required")
def test_playbook_upload_rag_isolation() -> None:
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    acme = client.post(
        "/auth/signup",
        json={
            "company_name": f"Acme {suffix}",
            "email": f"acme-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert acme.status_code == 200, acme.text
    acme_token = acme.json()["access_token"]
    acme_tenant = uuid.UUID(acme.json()["user"]["tenant"]["id"])

    beta = client.post(
        "/auth/signup",
        json={
            "company_name": f"Beta {suffix}",
            "email": f"beta-{suffix}@example.com",
            "password": "password123",
        },
    )
    assert beta.status_code == 200, beta.text
    beta_token = beta.json()["access_token"]
    beta_tenant = uuid.UUID(beta.json()["user"]["tenant"]["id"])
    assert acme_tenant != beta_tenant

    acme_md = (
        f"# Acme Secret Escalation {suffix}\n\n"
        f"Only Acme Corp uses the codeword ZEBRA-ACME-{suffix} for stockouts.\n"
    )
    beta_md = (
        f"# Beta Carrier Playbook {suffix}\n\n"
        f"Only Beta Corp uses the codeword ORBIT-BETA-{suffix} for delays.\n"
    )

    up_acme = client.post(
        "/playbooks",
        headers={"Authorization": f"Bearer {acme_token}"},
        files={"file": ("acme-escalation.md", io.BytesIO(acme_md.encode("utf-8")), "text/markdown")},
    )
    assert up_acme.status_code == 200, up_acme.text
    assert up_acme.json()["playbook"]["chunk_count"] >= 1

    up_beta = client.post(
        "/playbooks",
        headers={"Authorization": f"Bearer {beta_token}"},
        files={"file": ("beta-carrier.md", io.BytesIO(beta_md.encode("utf-8")), "text/markdown")},
    )
    assert up_beta.status_code == 200, up_beta.text

    listed = client.get(
        "/playbooks",
        headers={"Authorization": f"Bearer {acme_token}"},
    )
    assert listed.status_code == 200
    keys = {p["doc_key"] for p in listed.json()["playbooks"]}
    assert "acme-escalation" in keys
    assert "beta-carrier" not in keys

    factory = get_owner_session_factory(SYNC_URL)
    with factory() as session:
        apply_tenant_session(session, acme_tenant)
        hits = retrieve_playbooks(
            session,
            tenant_id=acme_tenant,
            query=f"ZEBRA-ACME-{suffix} stockout escalation",
            top_k=5,
            min_score=0.01,
        )
        assert hits, "Acme should retrieve its own playbook"
        assert all("ORBIT-BETA" not in h.content for h in hits)
        assert all(h.doc_key != "beta-carrier" for h in hits)
        assert any(f"ZEBRA-ACME-{suffix}" in h.content or "Acme" in h.title for h in hits)

        apply_tenant_session(session, beta_tenant)
        beta_hits = retrieve_playbooks(
            session,
            tenant_id=beta_tenant,
            query=f"ORBIT-BETA-{suffix} carrier delays",
            top_k=5,
            min_score=0.01,
        )
        assert beta_hits
        assert all("ZEBRA-ACME" not in h.content for h in beta_hits)
        assert all(h.doc_key != "acme-escalation" for h in beta_hits)
