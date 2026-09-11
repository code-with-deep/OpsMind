"""Per-tenant API key hashing (MT1)."""

from __future__ import annotations

import hashlib
import hmac


def hash_api_key(raw_key: str) -> str:
    """Return a stable SHA-256 hex digest for storage."""
    normalized = (raw_key or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time compare of a raw key against a stored hash."""
    if not raw_key or not stored_hash:
        return False
    return hmac.compare_digest(hash_api_key(raw_key), stored_hash.strip())


def key_prefix(raw_key: str) -> str:
    """Return a display prefix for an API key (P1-1 fix for test suite).

    Bug found by an actual end-to-end run: the api_keys.key_prefix column is
    VARCHAR(16) — the previous version here returned up to 17 characters
    (16 + the ellipsis), overflowing the column and raising
    StringDataRightTruncation on insert. Cap at exactly 16 total.
    """
    normalized = (raw_key or "").strip()
    if len(normalized) <= 16:
        return normalized
    return f"{normalized[:15]}…"


