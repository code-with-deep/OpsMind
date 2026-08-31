"""Sanitize retrieved playbook text against prompt-injection phrases (P5)."""

from __future__ import annotations

import re

_INJECTION_IN_DOCS = [
    (re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions"), "[FILTERED_INJECTION]"),
    (re.compile(r"(?i)disregard\s+(all\s+)?(previous|prior)\s+instructions"), "[FILTERED_INJECTION]"),
    (re.compile(r"(?i)system\s+prompt\s*:"), "[FILTERED_SYSTEM]"),
    (re.compile(r"(?i)you\s+are\s+now\s+unrestricted"), "[FILTERED_INJECTION]"),
    (re.compile(r"(?i)override\s+safety\s+policy"), "[FILTERED_INJECTION]"),
]


def sanitize_rag_text(text: str) -> str:
    """Neutralize injection-like phrases found inside retrieved documents."""
    out = text or ""
    for pattern, repl in _INJECTION_IN_DOCS:
        out = pattern.sub(repl, out)
    return out
