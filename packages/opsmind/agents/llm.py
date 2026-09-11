"""OpenAI-compatible chat client (Groq by default via LLM_API_BASE)."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# P1-6: retry transient failures (rate limit / server error) before giving up.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_BACKOFF_BASE_SECONDS = 0.5


class LLMError(RuntimeError):
    """LLM call failed or returned unusable content."""


def llm_configured(api_key: str | None) -> bool:
    return bool(api_key and api_key.strip())


def chat_json(
    *,
    api_key: str,
    api_base: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.1,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Call chat/completions and parse a JSON object from the assistant message.

    Retries on 429/5xx with exponential backoff (P1-6) before raising LLMError.
    """
    if not api_key.strip():
        raise LLMError("LLM_API_KEY is empty")

    base = api_base.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    for attempt in range(_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        "llm_retry model=%s status=%s attempt=%s delay=%.1fs",
                        model, resp.status_code, attempt + 1, delay,
                    )
                    time.sleep(delay)
                    continue
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:400]}") from exc
                data = resp.json()
            break
        except httpx.TransportError as exc:
            # Network-level failure (timeout, connection reset) — also retryable.
            if attempt < _MAX_RETRIES:
                delay = _BACKOFF_BASE_SECONDS * (2**attempt)
                logger.warning(
                    "llm_retry model=%s transport_error=%s attempt=%s delay=%.1fs",
                    model, exc, attempt + 1, delay,
                )
                time.sleep(delay)
                continue
            raise LLMError(f"LLM transport error after retries: {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {data!r}") from exc

    return _parse_json_object(content)


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
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise LLMError(f"Could not parse JSON from LLM content: {text[:300]}")
