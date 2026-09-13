"""Password hashing helpers (MT2) — PBKDF2-SHA256, no extra deps."""

from __future__ import annotations

import hashlib
import hmac
import secrets


_ITERATIONS = 210_000
_SALT_BYTES = 16

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def password_policy_error(password: str | None) -> str | None:
    """User-facing reason a *new* password is rejected, or None when acceptable.

    Mirrors ``passwordIssues`` in apps/web/src/lib/validation.ts — keep in sync.
    Applied only when choosing a password (signup, join, reset, change), never at
    login, so accounts created under older rules can still sign in.
    """
    value = password or ""
    if len(value) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if len(value) > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
    if value != value.strip():
        return "Password can't start or end with a space."
    if not any(ch.isalpha() for ch in value):
        return "Password must include at least one letter."
    if not any(ch.isdigit() for ch in value):
        return "Password must include at least one number."
    return None


def hash_password(password: str) -> str:
    """Return ``pbkdf2$iterations$salt_hex$hash_hex``."""
    normalized = (password or "").encode("utf-8")
    if len(normalized) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", normalized, salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not password or not stored:
        return False
    try:
        scheme, iter_s, salt_hex, hash_hex = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    try:
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(digest, expected)
