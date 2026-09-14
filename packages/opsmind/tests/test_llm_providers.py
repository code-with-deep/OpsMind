"""LLM provider chain: Gemini → OpenAI → Groq, then the caller's heuristic (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from opsmind.agents import llm
from opsmind.agents.llm import (
    LLMError,
    complete_json,
    configure_providers,
    llm_configured,
    providers_from_settings,
)


class Answer(BaseModel):
    answer: str


def _settings(**overrides):
    values = {
        "gemini_api_key": "gemini-secret",
        "openai_api_key": "openai-secret",
        "openai_api_base": "https://api.openai.com/v1",
        "llm_api_key": "groq-secret",
        "llm_api_base": "https://api.groq.com/openai/v1",
        "llm_model_fast": "groq-fast",
        "llm_model_strong": "groq-strong",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def _reset_providers():
    yield
    configure_providers([])


def _fake_post(outcomes: dict):
    """Replace the HTTP call: each provider returns reply text or raises an error."""
    calls: list[tuple[str, str]] = []

    def post(provider, payload):
        calls.append((provider.name, payload["model"]))
        outcome = outcomes[provider.name]
        if isinstance(outcome, Exception):
            raise outcome
        return {"choices": [{"message": {"content": outcome}}]}

    return post, calls


def test_default_order_is_gemini_then_openai_then_groq():
    assert [p.name for p in providers_from_settings(_settings())] == ["gemini", "openai", "groq"]


def test_providers_without_keys_are_skipped_and_legacy_key_configures_groq():
    providers = providers_from_settings(_settings(gemini_api_key="", openai_api_key=""))
    assert [(p.name, p.model_fast, p.model_strong) for p in providers] == [
        ("groq", "groq-fast", "groq-strong")
    ]


def test_custom_order_is_respected():
    order = providers_from_settings(_settings(llm_provider_order="groq, gemini"))
    assert [p.name for p in order] == ["groq", "gemini"]


def test_no_keys_means_llm_disabled():
    configure_providers(providers_from_settings(SimpleNamespace(llm_api_key="")))
    assert llm_configured({"llm_enabled": True}) is False


def test_gemini_is_used_first(monkeypatch):
    configure_providers(providers_from_settings(_settings()))
    post, calls = _fake_post(
        {"gemini": '{"answer": "gemini"}', "openai": '{"answer": "openai"}', "groq": '{"answer": "groq"}'}
    )
    monkeypatch.setattr(llm, "_post_chat_completions", post)

    result = complete_json(tier="strong", system="s", user="u", validate=Answer.model_validate)

    assert result.answer == "gemini"
    assert calls == [("gemini", "gemini-2.5-pro")]


def test_error_and_invalid_json_fall_through_to_groq(monkeypatch):
    configure_providers(providers_from_settings(_settings()))
    post, calls = _fake_post(
        {
            "gemini": LLMError("HTTP 503: overloaded"),
            "openai": "sorry, not JSON",
            "groq": '{"answer": "groq"}',
        }
    )
    monkeypatch.setattr(llm, "_post_chat_completions", post)

    result = complete_json(tier="fast", system="s", user="u", validate=Answer.model_validate)

    assert result.answer == "groq"
    assert calls == [("gemini", "gemini-2.5-flash"), ("openai", "gpt-4.1-mini"), ("groq", "groq-fast")]


def test_reply_that_fails_the_schema_counts_as_a_failure(monkeypatch):
    configure_providers(providers_from_settings(_settings(llm_api_key="")))
    post, _ = _fake_post({"gemini": '{"wrong_field": 1}', "openai": '{"answer": "openai"}'})
    monkeypatch.setattr(llm, "_post_chat_completions", post)

    result = complete_json(tier="fast", system="s", user="u", validate=Answer.model_validate)

    assert result.answer == "openai"


def test_all_providers_failing_raises_without_leaking_keys(monkeypatch):
    configure_providers(providers_from_settings(_settings()))
    post, _ = _fake_post({name: LLMError("HTTP 401: invalid key") for name in ("gemini", "openai", "groq")})
    monkeypatch.setattr(llm, "_post_chat_completions", post)

    with pytest.raises(LLMError) as err:
        complete_json(tier="fast", system="s", user="u", validate=Answer.model_validate)

    message = str(err.value)
    assert "gemini" in message and "openai" in message and "groq" in message
    assert not any(secret in message for secret in ("gemini-secret", "openai-secret", "groq-secret"))


def test_run_state_never_contains_api_keys():
    from opsmind.graph.runner import build_runtime

    runtime = build_runtime(
        _settings(
            database_url_sync="postgresql://x",
            database_url_readonly="postgresql://y",
            max_critic_retries=2,
            max_tool_calls_per_run=40,
        )
    )

    assert runtime["llm_enabled"] is True
    assert [entry.split(":")[0] for entry in runtime["llm_providers"]] == ["gemini", "openai", "groq"]
    assert not any(secret in str(runtime) for secret in ("gemini-secret", "openai-secret", "groq-secret"))
