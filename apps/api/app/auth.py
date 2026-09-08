"""API key + JWT authentication and tenant resolution (MT1/MT2)."""

from __future__ import annotations

import hmac
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.config import get_settings
from opsmind.auth.api_keys import hash_api_key
from opsmind.auth.jwt_tokens import decode_access_token, looks_like_jwt
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_models import ApiKey, Tenant, User
from opsmind.domain.tenant import TenantContext


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    auth = authorization.strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def resolve_tenant_from_api_key(session: Session, raw_key: str) -> TenantContext:
    """Look up tenant by hashed API key; fall back to env bootstrap for demo."""
    key_hash = hash_api_key(raw_key)
    row = session.execute(
        select(ApiKey, Tenant)
        .join(Tenant, Tenant.id == ApiKey.tenant_id)
        .where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    ).first()

    if row is not None:
        api_key, tenant = row
        if tenant.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is not active",
            )
        # Check if the key is associated with a user and that user is active
        if api_key.created_by is not None:
            from opsmind.db.tenant_models import User as UserModel  # local import to avoid circular
            owner = session.scalar(
                select(UserModel).where(UserModel.email == api_key.created_by)
            )
            if owner is not None and owner.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account access has been revoked.",
                )
        return TenantContext(
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            api_key_id=api_key.id,
            api_key_prefix=api_key.key_prefix,
            auth_method="api_key",
        )

    settings = get_settings()
    expected = (settings.opsmind_api_key or "").strip()
    if expected and hmac.compare_digest(raw_key, expected):
        tenant = session.scalar(select(Tenant).where(Tenant.slug == "demo"))
        if tenant is not None:
            return TenantContext(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                api_key_id=None,
                api_key_prefix=None,
                auth_method="api_key",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


def resolve_tenant_from_jwt(session: Session, token: str) -> TenantContext:
    settings = get_settings()
    secret = (settings.jwt_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET is not configured on the server",
        )
    try:
        payload = decode_access_token(token, secret=secret)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(str(payload["sub"]))
        tenant_id = uuid.UUID(str(payload["tenant_id"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    row = session.execute(
        select(User, Tenant)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(User.id == user_id, User.tenant_id == tenant_id)
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session is no longer valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user, tenant = row
    if tenant.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is not active",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account access has been revoked.",
        )
    return TenantContext(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        user_id=user.id,
        user_email=user.email,
        role=user.role,
        auth_method="jwt",
    )


def require_tenant_context(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> TenantContext:
    """Resolve TenantContext from API key or JWT — never trust client tenant ids."""
    api_key = (x_api_key or "").strip() or None
    bearer = _extract_bearer(authorization)
    settings = get_settings()
    factory = get_owner_session_factory(settings.database_url_sync)

    with factory() as session:
        if api_key:
            return resolve_tenant_from_api_key(session, api_key)

        if bearer:
            if looks_like_jwt(bearer):
                return resolve_tenant_from_jwt(session, bearer)
            return resolve_tenant_from_api_key(session, bearer)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_api_key(
    tenant: TenantContext = Depends(require_tenant_context),
) -> str:
    """Backward-compatible dependency used by older routes."""
    return tenant.tenant_slug


def require_admin(
    tenant: TenantContext = Depends(require_tenant_context),
) -> TenantContext:
    if tenant.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return tenant


def require_user_session(
    tenant: TenantContext = Depends(require_tenant_context),
) -> TenantContext:
    if tenant.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User session required (log in with email/password)",
        )
    return tenant
