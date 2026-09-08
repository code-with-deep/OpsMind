"""Notification routes — list, count unread, mark as read (MT access system)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.auth import require_user_session
from api.app.deps import get_tenant_session
from opsmind.db.tenant_models import Notification
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _notification_to_dict(n: Notification) -> dict[str, Any]:
    return {
        "id": str(n.id),
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "related_entity_id": str(n.related_entity_id) if n.related_entity_id else None,
        "related_entity_type": n.related_entity_type,
    }


@router.get("")
def list_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    tenant: TenantContext = Depends(require_user_session),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """List notifications for the authenticated user, ordered by newest first."""
    if tenant.user_id is None:
        raise HTTPException(status_code=403, detail="User session required")

    rows = session.scalars(
        select(Notification)
        .where(
            Notification.tenant_id == tenant.tenant_id,
            Notification.recipient_user_id == tenant.user_id,
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()

    return sanitize_output_payload(
        {"notifications": [_notification_to_dict(n) for n in rows], "count": len(rows)}
    )


@router.get("/unread-count")
def get_unread_count(
    tenant: TenantContext = Depends(require_user_session),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Fast unread notification count for the bell badge."""
    if tenant.user_id is None:
        raise HTTPException(status_code=403, detail="User session required")

    count = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.tenant_id == tenant.tenant_id,
            Notification.recipient_user_id == tenant.user_id,
            Notification.is_read.is_(False),
        )
    ) or 0

    return sanitize_output_payload({"count": count})


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: uuid.UUID,
    tenant: TenantContext = Depends(require_user_session),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Mark a single notification as read."""
    if tenant.user_id is None:
        raise HTTPException(status_code=403, detail="User session required")

    n = session.get(Notification, notification_id)
    if n is None or n.tenant_id != tenant.tenant_id or n.recipient_user_id != tenant.user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    n.is_read = True
    session.commit()
    return sanitize_output_payload({"read": True})


@router.post("/read-all")
def mark_all_notifications_read(
    tenant: TenantContext = Depends(require_user_session),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Mark all notifications for the authenticated user as read."""
    if tenant.user_id is None:
        raise HTTPException(status_code=403, detail="User session required")

    unread = session.scalars(
        select(Notification).where(
            Notification.tenant_id == tenant.tenant_id,
            Notification.recipient_user_id == tenant.user_id,
            Notification.is_read.is_(False),
        )
    ).all()

    for n in unread:
        n.is_read = True

    session.commit()
    return sanitize_output_payload({"marked_read": len(unread)})
