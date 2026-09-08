"""JWT helpers for web session auth (MT2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

ALGORITHM = "HS256"
AUDIENCE = "opsmind-web"
ISSUER = "opsmind"


def create_access_token(
    *,
    secret: str,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    email: str,
    role: str,
    expire_hours: int = 72,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": email,
        "role": role,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(hours=max(1, expire_hours)),
        "aud": AUDIENCE,
        "iss": ISSUER,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"require": ["exp", "iat", "nbf", "sub", "aud", "iss"]},
    )


def looks_like_jwt(token: str) -> bool:
    parts = (token or "").split(".")
    return len(parts) == 3 and all(parts)
