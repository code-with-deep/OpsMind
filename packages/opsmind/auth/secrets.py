"""Symmetric encryption for reversible secrets (warehouse DSNs — MT6)."""

from __future__ import annotations

import base64
import hashlib
import os
from urllib.parse import quote_plus

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    raw = (os.getenv("OPSMIND_SECRETS_KEY") or "").strip()
    if raw:
        try:
            return Fernet(raw.encode("utf-8"))
        except (ValueError, TypeError):
            digest = hashlib.sha256(raw.encode("utf-8")).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    seed = (os.getenv("JWT_SECRET") or "opsmind-dev-secrets-seed").encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(seed).digest()))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt((plaintext or "").encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt((ciphertext or "").encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt secret — check OPSMIND_SECRETS_KEY") from exc


def build_postgres_dsn(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
) -> str:
    user = quote_plus(username or "")
    pwd = quote_plus(password or "")
    return f"postgresql://{user}:{pwd}@{host}:{int(port)}/{database}"
