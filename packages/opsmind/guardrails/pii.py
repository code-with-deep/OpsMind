"""Basic PII redaction for logs / audit payloads (P5)."""

from __future__ import annotations

import re


_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_SSN_LIKE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_pii(text: str) -> str:
    out = text or ""
    out = _EMAIL.sub("[EMAIL_REDACTED]", out)
    out = _PHONE.sub("[PHONE_REDACTED]", out)
    out = _SSN_LIKE.sub("[SSN_REDACTED]", out)
    return out
