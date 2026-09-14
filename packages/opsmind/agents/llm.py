"""LLM access for the agents: Gemini first, then OpenAI, then Groq.

Every provider is called through its OpenAI-compatible chat/completions API. A
provider takes part only when its API key is set; a failed call — HTTP error,
timeout, or a reply that isn't the JSON the agent asked for — moves on to the
next provider, and when all of them fail the calling agent falls back to its
deterministic heuristic.

API keys live in this module's process-wide provider list (set by
``opsmind.graph.runner.build_runtime``), never in LangGraph state, which is
checkpointed to the database.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")
Tier = Literal["fast", "strong"]

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# One quick retry per provider — the next provider is the real fallback (P1-6).
_MAX_RETRIES = 1
_BACKOFF_BASE_SECONDS = 0.5
_TIMEOUT_SECONDS = 60.0

DEFAULT_PROVIDER_ORDER = ("gemini", "openai", "groq")
# name -> (api_base, fast model, strong model), used when settings leave them blank.
_PROVIDER_DEFAULTS = {
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ),
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini", "gpt-4.1"),
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "openai/gpt-oss-120b"),
}


class LLMError(RuntimeError):
    """An LLM call failed or returned unusable content."""


@dataclass(frozen=True)
class LLMProvider:
    name: str
    api_base: str
    api_key: str
    model_fast: str
    model_strong: str

    def model(self, tier: Tier) -> str:
        return self.model_fast if tier == "fast" else self.model_strong

    def describe(self) -> str:
        """Identifies the provider for logs and run metadata — never includes the key."""
        return f"{self.name}:{self.model_fast}/{self.model_strong}"


def providers_from_settings(settings: Any) -> list[LLMProvider]:
    """Providers with an API key, in ``llm_provider_order`` (default gemini,openai,groq).

    Gemini uses ``gemini_*`` settings, OpenAI the shared ``openai_api_key`` /
    ``openai_api_base`` plus ``openai_model_*``, and Groq ``groq_api_key`` or the
    legacy ``llm_api_key`` with ``llm_api_base`` / ``llm_model_*``.
    """

    def get(name: str) -> str:
        return str(getattr(settings, name, "") or "").strip()

    configs = {
        "gemini": (
            get("gemini_api_key"),
            get("gemini_api_base"),
            get("gemini_model_fast"),
            get("gemini_model_strong"),
        ),
        "openai": (
            get("openai_api_key"),
            get("openai_api_base"),
            get("openai_model_fast"),
            get("openai_model_strong"),
        ),
        "groq": (
            get("groq_api_key") or get("llm_api_key"),
            get("llm_api_base"),
            get("llm_model_fast"),
            get("llm_model_strong"),
        ),
    }
    order = get("llm_provider_order") or ",".join(DEFAULT_PROVIDER_ORDER)

    providers: list[LLMProvider] = []
    for name in (part.strip().lower() for part in order.split(",")):
        if not name:
            continue
        if name not in configs:
            logger.warning("llm_unknown_provider name=%s (expected one of %s)", name, list(configs))
            continue
        api_key, api_base, model_fast, model_strong = configs[name]
        if not api_key:
            continue
        default_base, default_fast, default_strong = _PROVIDER_DEFAULTS[name]
        providers.append(
            LLMProvider(
                name=name,
                api_base=(api_base or default_base).rstrip("/"),
                api_key=api_key,
                model_fast=model_fast or default_fast,
                model_strong=model_strong or default_strong,
            )
        )
    return providers


_providers: list[LLMProvider] = []
_providers_lock = threading.Lock()


def configure_providers(providers: list[LLMProvider]) -> None:
    global _providers
    with _providers_lock:
        _providers = list(providers)


def configured_providers() -> list[LLMProvider]:
    with _providers_lock:
        return list(_providers)


def llm_configured(runtime: dict[str, Any] | None = None) -> bool:
    """True when this run allows LLM calls and at least one provider has a key."""
    if runtime is not None and not runtime.get("llm_enabled"):
        return False
    return bool(configured_providers())


def complete_json(
    *,
    tier: Tier,
    system: str,
    user: str,
    validate: Callable[[dict[str, Any]], T],
    temperature: float = 0.1,
) -> T:
    """Ask each configured provider in turn for a JSON object that passes ``validate``.

    Raises LLMError (listing each provider's failure, without keys) when none succeed.
    """
    providers = configured_providers()
    if not providers:
        raise LLMError("No LLM provider has an API key configured")

    failures: list[str] = []
    for index, provider in enumerate(providers):
        model = provider.model(tier)
        try:
            result = validate(_chat(provider, model, system=system, user=user, temperature=temperature))
        except Exception as exc:  # noqa: BLE001 — any failure falls through to the next provider
            reason = (str(exc).splitlines() or [type(exc).__name__])[0][:300]
            failures.append(f"{provider.name}/{model}: {reason}")
            logger.warning("llm_provider_failed provider=%s model=%s error=%s", provider.name, model, reason)
            continue
        if index:
            logger.warning(
                "llm_fallback_used provider=%s model=%s after=%s", provider.name, model, "; ".join(failures)
            )
        else:
            logger.info("llm_call provider=%s model=%s", provider.name, model)
        return result

    raise LLMError("All LLM providers failed — " + " | ".join(failures))


def _chat(provider: LLMProvider, model: str, *, system: str, user: str, temperature: float) -> dict[str, Any]:
    payload = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    data = _post_chat_completions(provider, payload)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("unexpected response shape from chat/completions") from exc
    return _parse_json_object(content)


def _post_chat_completions(provider: LLMProvider, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{provider.api_base}/chat/completions"
    headers = {"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"}

    for attempt in range(_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.TransportError as exc:
            if attempt < _MAX_RETRIES:
                _backoff(provider, attempt, f"transport_error={exc}")
                continue
            raise LLMError(f"transport error: {exc}") from exc

        if resp.status_code == 400 and "response_format" in payload and "response_format" in resp.text:
            # Endpoint without JSON mode: the prompt already demands JSON, so retry without it.
            payload = {key: value for key, value in payload.items() if key != "response_format"}
            continue
        if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
            _backoff(provider, attempt, f"status={resp.status_code}")
            continue
        if resp.is_error:
            raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise LLMError("chat/completions response was not JSON") from exc

    raise LLMError("retries exhausted")


def _backoff(provider: LLMProvider, attempt: int, reason: str) -> None:
    delay = _BACKOFF_BASE_SECONDS * (2**attempt)
    logger.warning("llm_retry provider=%s %s attempt=%s delay=%.1fs", provider.name, reason, attempt + 1, delay)
    time.sleep(delay)


def _parse_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        raise LLMError("Empty LLM content")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"Could not parse JSON from LLM content: {text[:300]}") from exc
        if isinstance(parsed, dict):
            return parsed
    raise LLMError(f"Could not parse JSON from LLM content: {text[:300]}")
