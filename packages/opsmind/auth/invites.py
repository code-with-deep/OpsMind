"""Invite code helpers (MT2)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import string


def generate_invite_code() -> str:
    """Human-friendly invite code, e.g. ``OM-A7K2-9MQX``."""
    alphabet = string.ascii_uppercase + string.digits
    # Avoid ambiguous chars
    alphabet = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
    left = "".join(secrets.choice(alphabet) for _ in range(4))
    right = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"OM-{left}-{right}"


def hash_invite_code(raw_code: str) -> str:
    normalized = (raw_code or "").strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def verify_invite_code(raw_code: str, stored_hash: str) -> bool:
    if not raw_code or not stored_hash:
        return False
    return hmac.compare_digest(hash_invite_code(raw_code), stored_hash.strip())


def invite_prefix(raw_code: str) -> str:
    normalized = (raw_code or "").strip().upper()
    if len(normalized) <= 7:
        return normalized
    return f"{normalized[:7]}…"
