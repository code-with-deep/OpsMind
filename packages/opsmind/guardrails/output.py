"""Output guardrails — strip secrets / unsafe leakage from responses (P5)."""

from __future__ import annotations

import re
from typing import Any


_SECRET_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?([^\s'\"]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)gsk_[A-Za-z0-9]+"), "gsk_[REDACTED]"),
    (re.compile(r"(?i)sk-[A-Za-z0-9]+"), "sk-[REDACTED]"),
    (
        re.compile(
            r"(?i)postgres(?:ql)?(?:\+[\w]+)?://[^\s]+"
        ),
        "postgresql://[REDACTED]",
    ),
]


def redact_secrets(text: str) -> str:
    out = text or ""
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def sanitize_output_payload(payload: Any) -> Any:
    """Recursively redact secret-looking strings in API/graph payloads."""
    if isinstance(payload, str):
        return redact_secrets(payload)
    if isinstance(payload, list):
        return [sanitize_output_payload(x) for x in payload]
    if isinstance(payload, dict):
        return {k: sanitize_output_payload(v) for k, v in payload.items()}
    return payload
