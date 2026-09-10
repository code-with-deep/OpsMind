"""Password reset token helpers — hash-at-rest, invite-style."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_reset_token() -> str:
    """Opaque URL-safe token (shown once in email link)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw_token: str) -> str:
    normalized = (raw_token or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_reset_token(raw_token: str, stored_hash: str) -> bool:
    if not raw_token or not stored_hash:
        return False
    return hmac.compare_digest(hash_reset_token(raw_token), stored_hash.strip())


def reset_token_prefix(raw_token: str) -> str:
    normalized = (raw_token or "").strip()
    if len(normalized) <= 8:
        return normalized
    return f"{normalized[:8]}…"
