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
from opsmind.auth.email import build_password_reset_email, send_email
from opsmind.auth.invites import (
    generate_invite_code,
    hash_invite_code,
    invite_prefix,
)
from opsmind.auth.jwt_tokens import create_access_token
from opsmind.auth.password_reset import (
    generate_reset_token,
    hash_reset_token,
    reset_token_prefix,
)
from opsmind.auth.passwords import hash_password, verify_password
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_models import (
    AccessRequest,
    InviteCode,
    Notification,
    PasswordResetToken,
    Tenant,
    TenantSettings,
    User,
)
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/auth", tags=["auth"])

_SLUG_RE = re.compile(r"[^a-z0-9-]+")
_FORGOT_GENERIC = (
    "If an account exists for that email, we sent a password reset link."
)


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
        token_version=int(user.token_version or 0),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_hours": settings.jwt_expire_hours,
        "user": _user_payload(user, tenant),
    }


def _revoke_open_reset_tokens(session: Session, user_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    rows = session.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all()
    for row in rows:
        row.used_at = now


def _set_password(session: Session, user: User, new_password: str) -> None:
    try:
        user.password_hash = hash_password(new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user.password_changed_at = datetime.now(timezone.utc)
    user.token_version = int(user.token_version or 0) + 1
    _revoke_open_reset_tokens(session, user.id)


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


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


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
        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account access has been revoked. Please contact your workspace admin.",
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


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    tenant: TenantContext = Depends(require_user_session),
) -> dict[str, Any]:
    """Logged-in user changes password (Settings). Returns a fresh JWT."""
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password",
        )
    settings = get_settings()
    factory = get_owner_session_factory(settings.database_url_sync)
    with factory() as session:
        row = session.execute(
            select(User, Tenant)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(User.id == tenant.user_id, User.tenant_id == tenant.tenant_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=401, detail="Session invalid")
        user, t = row
        if not verify_password(body.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )
        _set_password(session, user, body.new_password)
        session.commit()
        session.refresh(user)
        session.refresh(t)
        return sanitize_output_payload(_issue_token(user, t))


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordBody) -> dict[str, Any]:
    """Request a password-reset email. Always returns a generic message."""
    settings = get_settings()
    email = str(body.email).strip().lower()
    factory = get_owner_session_factory(settings.database_url_sync)
    generic = {"message": _FORGOT_GENERIC}

    with factory() as session:
        row = session.execute(
            select(User, Tenant)
            .join(Tenant, Tenant.id == User.tenant_id)
            .where(User.email == email)
        ).first()
        if row is None:
            return sanitize_output_payload(generic)

        user, t = row
        if not user.password_hash or t.status != "active":
            return sanitize_output_payload(generic)

        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        recent = session.scalar(
            select(func.count())
            .select_from(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.created_at >= hour_ago,
            )
        ) or 0
        if int(recent) >= settings.auth_password_reset_max_per_hour:
            return sanitize_output_payload(generic)

        raw = generate_reset_token()
        ttl = max(5, int(settings.auth_password_reset_ttl_minutes))
        token_row = PasswordResetToken(
            id=uuid.uuid4(),
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            token_prefix=reset_token_prefix(raw),
            expires_at=now + timedelta(minutes=ttl),
        )
        session.add(token_row)
        session.commit()

        base = (settings.app_public_url or "http://localhost:3000").rstrip("/")
        reset_url = f"{base}/reset-password?token={raw}"
        subject, text_body = build_password_reset_email(
            reset_url=reset_url,
            ttl_minutes=ttl,
            app_name=settings.app_name or "OpsMind",
        )
        try:
            send_email(
                to_address=user.email,
                subject=subject,
                body_text=text_body,
                from_address=settings.email_from,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_username=settings.smtp_username,
                smtp_password=settings.smtp_password,
                smtp_use_tls=settings.smtp_use_tls,
            )
        except Exception:
            return sanitize_output_payload(generic)

    return sanitize_output_payload(generic)


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody) -> dict[str, Any]:
    """Consume a reset token and set a new password. User must log in after."""
    settings = get_settings()
    raw = body.token.strip()
    factory = get_owner_session_factory(settings.database_url_sync)

    with factory() as session:
        token_row = session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_reset_token(raw),
                PasswordResetToken.used_at.is_(None),
            )
        )
        if token_row is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset link",
            )
        now = datetime.now(timezone.utc)
        expires = token_row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset link",
            )

        user = session.get(User, token_row.user_id)
        tenant = session.get(Tenant, token_row.tenant_id)
        if user is None or tenant is None or tenant.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset link",
            )

        _set_password(session, user, body.new_password)
        token_row.used_at = now
        session.commit()

    return sanitize_output_payload(
        {
            "message": "Password updated. You can sign in with your new password.",
        }
    )


@router.post("/join")
def join_with_invite(body: JoinInviteBody) -> dict[str, Any]:
    """Redeem invite code → create AccessRequest (pending admin approval). No JWT returned."""
    settings = get_settings()
    email = str(body.email).strip().lower()
    code = body.invite_code.strip().upper()
    factory = get_owner_session_factory(settings.database_url_sync)

    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with factory() as session:
        # Block if email already has an active user account
        existing_user = session.scalar(select(User).where(User.email == email))
        if existing_user is not None:
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

        # Check for any existing access request for this email in this tenant (any status)
        existing_request = session.scalar(
            select(AccessRequest).where(
                AccessRequest.tenant_id == tenant.id,
                AccessRequest.requester_email == email,
            )
        )
        if existing_request is not None:
            if existing_request.status == "approved":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email has already been approved — please sign in with your credentials.",
                )
            if existing_request.status == "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An access request for this email is already pending. Please wait for admin review.",
                )
            # status == "rejected" → re-open the request with new credentials
            # Reset all review fields so it enters the queue fresh
            now = datetime.now(timezone.utc)
            existing_request.status = "pending"
            existing_request.password_hash = password_hash
            existing_request.invite_code_id = invite.id
            existing_request.reviewed_by = None
            existing_request.reviewed_at = None
            existing_request.rejection_reason = None
            existing_request.created_at = now
            existing_request.user_id = None
            invite.use_count += 1

            # Notify admins about the re-submitted request
            admin_users = session.scalars(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.role == "admin",
                    User.status == "active",
                )
            ).all()
            for admin in admin_users:
                session.add(
                    Notification(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        recipient_user_id=admin.id,
                        type="access_request_submitted",
                        title="Access request re-submitted",
                        body=f"{email} has re-submitted an access request to your workspace.",
                        related_entity_id=existing_request.id,
                        related_entity_type="access_request",
                        is_read=False,
                    )
                )

            session.commit()
            session.refresh(existing_request)
            return sanitize_output_payload(
                {
                    "status": "pending",
                    "message": "Access request re-submitted successfully. An admin will review it shortly.",
                    "request_id": str(existing_request.id),
                }
            )

        # No existing request — create a fresh one
        access_request = AccessRequest(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            invite_code_id=invite.id,
            requester_email=email,
            password_hash=password_hash,
            status="pending",
        )
        invite.use_count += 1
        session.add(access_request)

        # Notify all admins in this tenant
        admin_users = session.scalars(
            select(User).where(
                User.tenant_id == tenant.id,
                User.role == "admin",
                User.status == "active",
            )
        ).all()
        for admin in admin_users:
            session.add(
                Notification(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    recipient_user_id=admin.id,
                    type="access_request_submitted",
                    title="New access request",
                    body=f"{email} is requesting access to your workspace.",
                    related_entity_id=access_request.id,
                    related_entity_type="access_request",
                    is_read=False,
                )
            )

        session.commit()
        session.refresh(access_request)
        return sanitize_output_payload(
            {
                "status": "pending",
                "message": "Access request submitted. You will be notified when an admin reviews your request.",
                "request_id": str(access_request.id),
            }
        )


@router.get("/request-status")
def get_request_status(email: str, invite_code: str) -> dict[str, Any]:
    """Poll access request status (no auth required — public, rate-limit by IP if needed later)."""
    settings = get_settings()
    normalized_email = email.strip().lower()
    code = invite_code.strip().upper()
    factory = get_owner_session_factory(settings.database_url_sync)

    with factory() as session:
        invite = session.scalar(
            select(InviteCode).where(
                InviteCode.code_hash == hash_invite_code(code),
            )
        )
        if invite is None:
            raise HTTPException(status_code=404, detail="Invite code not found")

        req = session.scalar(
            select(AccessRequest).where(
                AccessRequest.tenant_id == invite.tenant_id,
                AccessRequest.requester_email == normalized_email,
            )
        )
        if req is None:
            raise HTTPException(status_code=404, detail="No access request found for this email")

        return sanitize_output_payload(
            {
                "status": req.status,
                "message": (
                    "Your access request is pending admin review."
                    if req.status == "pending"
                    else "Your access request has been approved. You can now sign in."
                    if req.status == "approved"
                    else "Your access request was rejected."
                ),
                "rejection_reason": req.rejection_reason if req.status == "rejected" else None,
            }
        )


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


