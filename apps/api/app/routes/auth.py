"""Auth API — signup, login, invites (MT2)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.auth import require_admin, require_tenant_context, require_user_session
from api.app.config import get_settings
from api.app.deps import get_tenant_session
from opsmind.auth.api_keys import generate_api_key, hash_api_key, key_prefix
from opsmind.auth.invites import (
    generate_invite_code,
    hash_invite_code,
    invite_prefix,
)
from opsmind.auth.jwt_tokens import create_access_token
from opsmind.auth.passwords import hash_password, verify_password
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_models import ApiKey, InviteCode, Tenant, TenantSettings, User
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/auth", tags=["auth"])

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(name: str) -> str:
    base = (name or "").strip().lower().replace(" ", "-")
    base = _SLUG_RE.sub("", base).strip("-")
    base = re.sub(r"-{2,}", "-", base)
    if not base:
        base = "company"
    return base[:48]


def _unique_slug(session: Session, name: str) -> str:
    base = _slugify(name)
    candidate = base
    n = 2
    while session.scalar(select(Tenant.id).where(Tenant.slug == candidate)):
        candidate = f"{base}-{n}"[:64]
        n += 1
    return candidate


def _user_payload(user: User, tenant: Tenant) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
        },
    }


def _issue_token(user: User, tenant: Tenant) -> dict[str, Any]:
    settings = get_settings()
    token = create_access_token(
        secret=settings.jwt_secret,
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        role=user.role,
        expire_hours=settings.jwt_expire_hours,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_hours": settings.jwt_expire_hours,
        "user": _user_payload(user, tenant),
    }


class SignupBody(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class JoinInviteBody(BaseModel):
    invite_code: str = Field(min_length=6, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class CreateInviteBody(BaseModel):
    max_uses: int | None = Field(default=None, ge=1, le=100)
    ttl_days: int | None = Field(default=None, ge=1, le=90)


@router.post("/signup")
def signup(body: SignupBody) -> dict[str, Any]:
    """Self-serve signup: create tenant + admin user, return JWT."""
    settings = get_settings()
    email = str(body.email).strip().lower()
    factory = get_owner_session_factory(settings.database_url_sync)

    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with factory() as session:
        existing = session.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered — log in or use a different email",
            )

        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        slug = _unique_slug(session, body.company_name)
        tenant = Tenant(
            id=tenant_id,
            name=body.company_name.strip(),
            slug=slug,
            status="active",
            domain_profile="ecommerce",
        )
        session.add(tenant)
        session.add(
            TenantSettings(
                tenant_id=tenant_id,
                supported_domains=[
                    "revenue",
                    "inventory",
                    "fulfillment",
                    "returns",
                    "campaigns",
                ],
                enabled_sql_templates=[],
                soft_limits={
                    "max_active_invites": settings.auth_max_active_invites,
                    "max_investigations_per_day": 50,
                    "max_playbooks": settings.playbook_max_count,
                    "max_playbook_upload_bytes": settings.playbook_max_upload_mb
                    * 1024
                    * 1024,
                    "max_csv_upload_bytes": settings.csv_max_upload_mb * 1024 * 1024,
                    "max_csv_rows": settings.csv_max_rows,
                    "max_api_keys": settings.auth_max_api_keys,
                },
            )
        )
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            role="admin",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.refresh(tenant)
        return sanitize_output_payload(_issue_token(user, tenant))


@router.post("/login")
def login(body: LoginBody) -> dict[str, Any]:
    settings = get_settings()
    email = str(body.email).strip().lower()
    factory = get_owner_session_factory(settings.database_url_sync)

    with factory() as session:
        row = session.execute(
            select(User, Tenant)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(User.email == email)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        user, tenant = row
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if tenant.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is not active",
            )
        return sanitize_output_payload(_issue_token(user, tenant))


@router.get("/me")
def me(tenant: TenantContext = Depends(require_user_session)) -> dict[str, Any]:
    settings = get_settings()
    factory = get_owner_session_factory(settings.database_url_sync)
    with factory() as session:
        user = session.get(User, tenant.user_id)
        t = session.get(Tenant, tenant.tenant_id)
        if user is None or t is None:
            raise HTTPException(status_code=401, detail="Session invalid")
        return sanitize_output_payload({"user": _user_payload(user, t)})


@router.post("/join")
def join_with_invite(body: JoinInviteBody) -> dict[str, Any]:
    """Redeem invite code → Investigator in that tenant only."""
    settings = get_settings()
    email = str(body.email).strip().lower()
    code = body.invite_code.strip().upper()
    factory = get_owner_session_factory(settings.database_url_sync)

    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with factory() as session:
        existing = session.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already belongs to a company — one user per company in MVP",
            )

        invite = session.scalar(
            select(InviteCode).where(
                InviteCode.code_hash == hash_invite_code(code),
                InviteCode.revoked_at.is_(None),
            )
        )
        if invite is None:
            raise HTTPException(status_code=400, detail="Invalid invite code")

        now = datetime.now(timezone.utc)
        if invite.expires_at is not None and invite.expires_at <= now:
            raise HTTPException(status_code=400, detail="Invite code has expired")
        if invite.use_count >= invite.max_uses:
            raise HTTPException(status_code=400, detail="Invite code has no uses left")

        tenant = session.get(Tenant, invite.tenant_id)
        if tenant is None or tenant.status != "active":
            raise HTTPException(status_code=400, detail="Invite tenant is not active")

        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=email,
            password_hash=password_hash,
            role="investigator",
        )
        invite.use_count += 1
        session.add(user)
        session.commit()
        session.refresh(user)
        return sanitize_output_payload(_issue_token(user, tenant))


@router.post("/invites")
def create_invite(
    body: CreateInviteBody,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    settings = get_settings()
    active_count = session.scalar(
        select(func.count())
        .select_from(InviteCode)
        .where(
            InviteCode.tenant_id == tenant.tenant_id,
            InviteCode.revoked_at.is_(None),
        )
    ) or 0
    max_active = settings.auth_max_active_invites
    if active_count >= max_active:
        raise HTTPException(
            status_code=400,
            detail=f"Soft limit: at most {max_active} active invite codes",
        )

    raw = generate_invite_code()
    max_uses = body.max_uses or settings.auth_invite_default_max_uses
    ttl = body.ttl_days or settings.auth_invite_default_ttl_days
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl)

    invite = InviteCode(
        id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        code_hash=hash_invite_code(raw),
        code_prefix=invite_prefix(raw),
        expires_at=expires_at,
        max_uses=max_uses,
        use_count=0,
        created_by=tenant.user_id,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)

    return sanitize_output_payload(
        {
            "invite": {
                "id": str(invite.id),
                "code": raw,  # shown once
                "code_prefix": invite.code_prefix,
                "max_uses": invite.max_uses,
                "use_count": invite.use_count,
                "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
                "created_at": invite.created_at.isoformat() if invite.created_at else None,
            },
            "message": "Copy this invite code now — it will not be shown again.",
        }
    )


@router.get("/invites")
def list_invites(
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    rows = session.scalars(
        select(InviteCode)
        .where(InviteCode.tenant_id == tenant.tenant_id)
        .order_by(InviteCode.created_at.desc())
    ).all()
    items = [
        {
            "id": str(r.id),
            "code_prefix": r.code_prefix,
            "max_uses": r.max_uses,
            "use_count": r.use_count,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
            "active": r.revoked_at is None
            and (r.expires_at is None or r.expires_at > datetime.now(timezone.utc))
            and r.use_count < r.max_uses,
        }
        for r in rows
    ]
    return sanitize_output_payload({"invites": items, "count": len(items)})


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(
    invite_id: uuid.UUID,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    invite = session.get(InviteCode, invite_id)
    if invite is None or invite.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
        session.commit()
    return sanitize_output_payload(
        {
            "id": str(invite.id),
            "revoked": True,
            "revoked_at": invite.revoked_at.isoformat() if invite.revoked_at else None,
        }
    )


class UpdateTenantBody(BaseModel):
    name: str = Field(min_length=2, max_length=255)


@router.patch("/tenant")
def update_tenant_profile(
    body: UpdateTenantBody,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    row = session.get(Tenant, tenant.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    name = body.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Company name too short")
    row.name = name
    session.commit()
    session.refresh(row)
    return sanitize_output_payload(
        {
            "tenant": {
                "id": str(row.id),
                "name": row.name,
                "slug": row.slug,
            }
        }
    )


class CreateApiKeyBody(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=128)


@router.post("/api-keys")
def create_api_key(
    body: CreateApiKeyBody,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    settings = get_settings()
    ts = session.get(TenantSettings, tenant.tenant_id)
    limits = dict(ts.soft_limits or {}) if ts else {}
    max_keys = int(limits.get("max_api_keys") or settings.auth_max_api_keys)

    active_count = session.scalar(
        select(func.count())
        .select_from(ApiKey)
        .where(ApiKey.tenant_id == tenant.tenant_id, ApiKey.revoked_at.is_(None))
    ) or 0
    if int(active_count) >= max_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Soft limit: at most {max_keys} active API keys",
        )

    raw = generate_api_key()
    row = ApiKey(
        id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        name=(body.name or "default").strip()[:128],
        key_hash=hash_api_key(raw),
        key_prefix=key_prefix(raw),
        scopes={},
        created_by=str(tenant.user_id) if tenant.user_id else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return sanitize_output_payload(
        {
            "api_key": {
                "id": str(row.id),
                "name": row.name,
                "key": raw,
                "key_prefix": row.key_prefix,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            },
            "message": "Copy this API key now — it will not be shown again.",
        }
    )


@router.get("/api-keys")
def list_api_keys(
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    rows = session.scalars(
        select(ApiKey)
        .where(ApiKey.tenant_id == tenant.tenant_id)
        .order_by(ApiKey.created_at.desc())
    ).all()
    items = [
        {
            "id": str(r.id),
            "name": r.name,
            "key_prefix": r.key_prefix,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
            "active": r.revoked_at is None,
        }
        for r in rows
    ]
    return sanitize_output_payload({"api_keys": items, "count": len(items)})


@router.post("/api-keys/{key_id}/revoke")
def revoke_api_key(
    key_id: uuid.UUID,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    row = session.get(ApiKey, key_id)
    if row is None or row.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=404, detail="API key not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        session.commit()
    return sanitize_output_payload(
        {
            "id": str(row.id),
            "revoked": True,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        }
    )
