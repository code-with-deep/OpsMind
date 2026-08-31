"""OpenAI-compatible chat client (Groq by default via LLM_API_BASE)."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx


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
    """Call chat/completions and parse a JSON object from the assistant message."""
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
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:400]}") from exc
        data = resp.json()

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
