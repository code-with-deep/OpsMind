import pytest
from fastapi.testclient import TestClient

from api.app.config import clear_settings_cache
from api.app.main import create_app


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must supply env — Settings has no hardcoded defaults."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_NAME", "OpsMind")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://opsmind:opsmind@localhost:5432/opsmind",
    )
    monkeypatch.setenv(
        "DATABASE_URL_SYNC",
        "postgresql://opsmind:opsmind@localhost:5432/opsmind",
    )
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
    monkeypatch.setenv("OPSMIND_API_KEY", "test-opsmind-api-key")
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_health_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "OpsMind"


def test_root_links():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["health"] == "/health"
    assert body["ready"] == "/ready"
