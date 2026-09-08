"""Access management routes — approve/reject access requests, list/revoke users (MT access)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.auth import require_admin
from api.app.deps import get_tenant_session
from opsmind.db.tenant_models import AccessRequest, InviteCode, Notification, User
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/access", tags=["access"])


class RejectBody(BaseModel):
    reason: Optional[str] = None


class RevokeBody(BaseModel):
    reason: Optional[str] = None


def _request_to_dict(req: AccessRequest, session: Session) -> dict[str, Any]:
    reviewer_email: Optional[str] = None
    if req.reviewed_by:
        reviewer = session.get(User, req.reviewed_by)
        reviewer_email = reviewer.email if reviewer else None

    invite_prefix: Optional[str] = None
    if req.invite_code_id:
        invite = session.get(InviteCode, req.invite_code_id)
        invite_prefix = invite.code_prefix if invite else None

    return {
        "id": str(req.id),
        "requester_email": req.requester_email,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        "reviewed_by_email": reviewer_email,
        "rejection_reason": req.rejection_reason,
        "invite_code_prefix": invite_prefix,
    }


@router.get("/requests")
def list_access_requests(
    status_filter: str = Query(default="pending", alias="status"),
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """List access requests for this tenant. Filter by status (pending|approved|rejected|all)."""
    q = select(AccessRequest).where(AccessRequest.tenant_id == tenant.tenant_id)
    if status_filter != "all":
        q = q.where(AccessRequest.status == status_filter)
    q = q.order_by(AccessRequest.created_at.desc())

    rows = session.scalars(q).all()
    return sanitize_output_payload(
        {
            "requests": [_request_to_dict(r, session) for r in rows],
            "count": len(rows),
        }
    )


@router.post("/requests/{request_id}/approve")
def approve_access_request(
    request_id: uuid.UUID,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Approve a pending access request — creates the Investigator user."""
    req = session.get(AccessRequest, request_id)
    if req is None or req.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Access request not found")
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request already reviewed (status: {req.status})",
        )

    # Check email not already a User (race condition guard)
    existing = session.scalar(select(User).where(User.email == req.requester_email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    now = datetime.now(timezone.utc)
    new_user = User(
        id=uuid.uuid4(),
        tenant_id=req.tenant_id,
        email=req.requester_email,
        password_hash=req.password_hash,
        role="investigator",
        status="active",
    )
    session.add(new_user)
    session.flush()  # get new_user.id

    req.status = "approved"
    req.reviewed_by = tenant.user_id
    req.reviewed_at = now
    req.user_id = new_user.id

    # Notify the newly created user
    session.add(
        Notification(
            id=uuid.uuid4(),
            tenant_id=req.tenant_id,
            recipient_user_id=new_user.id,
            type="access_approved",
            title="Access approved",
            body="Your access request has been approved. You can now sign in.",
            related_entity_id=req.id,
            related_entity_type="access_request",
            is_read=False,
        )
    )

    session.commit()
    return sanitize_output_payload({"status": "approved", "user_id": str(new_user.id)})


@router.post("/requests/{request_id}/reject")
def reject_access_request(
    request_id: uuid.UUID,
    body: RejectBody,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Reject a pending access request with an optional reason."""
    req = session.get(AccessRequest, request_id)
    if req is None or req.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Access request not found")
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request already reviewed (status: {req.status})",
        )

    req.status = "rejected"
    req.reviewed_by = tenant.user_id
    req.reviewed_at = datetime.now(timezone.utc)
    if body.reason:
        req.rejection_reason = body.reason.strip()[:512]

    session.commit()
    return sanitize_output_payload({"status": "rejected"})


@router.get("/users")
def list_access_users(
    status_filter: str = Query(default="all", alias="status"),
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """List all users for this tenant with access info."""
    q = select(User).where(User.tenant_id == tenant.tenant_id)
    if status_filter != "all":
        q = q.where(User.status == status_filter)
    q = q.order_by(User.created_at.asc())

    rows = session.scalars(q).all()
    result = []
    for u in rows:
        # Look up the access request for this user (if any)
        req = session.scalar(
            select(AccessRequest).where(
                AccessRequest.user_id == u.id,
                AccessRequest.status == "approved",
            )
        )
        approved_by_email: Optional[str] = None
        if req and req.reviewed_by:
            reviewer = session.get(User, req.reviewed_by)
            approved_by_email = reviewer.email if reviewer else None

        result.append(
            {
                "id": str(u.id),
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "revoked_at": u.revoked_at.isoformat() if u.revoked_at else None,
                "invite_date": req.created_at.isoformat() if req and req.created_at else None,
                "approved_at": req.reviewed_at.isoformat() if req and req.reviewed_at else None,
                "approved_by_email": approved_by_email,
            }
        )
    return sanitize_output_payload({"users": result, "count": len(result)})


@router.post("/users/{user_id}/revoke")
def revoke_user_access(
    user_id: uuid.UUID,
    body: RevokeBody,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Revoke a user's access. Cannot revoke self or another admin."""
    if tenant.user_id is None:
        raise HTTPException(status_code=403, detail="Admin user session required")

    target = session.get(User, user_id)
    if target is None or target.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == tenant.user_id:
        raise HTTPException(status_code=400, detail="Cannot revoke your own access")
    if target.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot revoke another admin's access")
    if target.status == "revoked":
        # Already revoked — idempotent
        return sanitize_output_payload({"revoked": True})

    now = datetime.now(timezone.utc)
    target.status = "revoked"
    target.revoked_at = now
    target.revoked_by = tenant.user_id

    # Notify the revoked user
    session.add(
        Notification(
            id=uuid.uuid4(),
            tenant_id=tenant.tenant_id,
            recipient_user_id=target.id,
            type="access_revoked",
            title="Access revoked",
            body="Your access to the workspace has been revoked by an administrator.",
            related_entity_id=None,
            related_entity_type=None,
            is_read=False,
        )
    )

    session.commit()
    return sanitize_output_payload({"revoked": True})
