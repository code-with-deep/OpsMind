"""Per-tenant API key hashing (MT1) + generation (MT5)."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_api_key() -> str:
    """Opaque API key shown once, e.g. ``omk_…``."""
    return f"omk_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """Return a stable SHA-256 hex digest for storage."""
    normalized = (raw_key or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time compare of a raw key against a stored hash."""
    if not raw_key or not stored_hash:
        return False
    return hmac.compare_digest(hash_api_key(raw_key), stored_hash.strip())


def key_prefix(raw_key: str, *, length: int = 12) -> str:
    """Display prefix for operator UI (MT5)."""
    normalized = (raw_key or "").strip()
    if len(normalized) <= length:
        return normalized
    return f"{normalized[:length]}…"
