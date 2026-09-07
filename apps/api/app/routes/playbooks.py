"""Playbook upload / list / delete (MT3)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.app.auth import require_admin, require_tenant_context
from api.app.config import get_settings
from api.app.deps import get_tenant_session
from opsmind.db.ingest_playbooks import (
    delete_playbook,
    ingest_playbook_markdown,
    safe_doc_key,
    tenant_playbook_path,
)
from opsmind.db.memory_models import Document, DocumentChunk
from opsmind.db.tenant_models import TenantSettings
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/playbooks", tags=["playbooks"])

_ALLOWED_SUFFIXES = {".md", ".markdown", ".txt"}


def _soft_limits(session: Session, tenant_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    row = session.get(TenantSettings, tenant_id)
    limits = dict(row.soft_limits or {}) if row else {}
    limits.setdefault("max_playbooks", settings.playbook_max_count)
    limits.setdefault(
        "max_playbook_upload_bytes",
        settings.playbook_max_upload_mb * 1024 * 1024,
    )
    return limits


def _document_payload(doc: Document, chunk_count: int) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "doc_key": doc.doc_key,
        "title": doc.title,
        "chunk_count": chunk_count,
        "content_hash": doc.content_hash,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


@router.get("")
def list_playbooks(
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    docs = session.scalars(
        select(Document)
        .where(Document.tenant_id == tenant.tenant_id)
        .order_by(Document.updated_at.desc())
    ).all()
    counts = {
        row.document_id: int(row.n)
        for row in session.execute(
            select(DocumentChunk.document_id, func.count().label("n"))
            .where(DocumentChunk.tenant_id == tenant.tenant_id)
            .group_by(DocumentChunk.document_id)
        ).all()
    }
    items = [_document_payload(d, counts.get(d.id, 0)) for d in docs]
    return sanitize_output_payload({"playbooks": items, "count": len(items)})


@router.post("")
async def upload_playbook(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    filename = file.filename or "playbook.md"
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Markdown (.md) or plain text (.txt) playbooks are supported",
        )

    limits = _soft_limits(session, tenant.tenant_id)
    max_bytes = int(limits["max_playbook_upload_bytes"])
    max_count = int(limits["max_playbooks"])

    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Playbook exceeds soft limit of {max_bytes} bytes",
        )
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playbook must be UTF-8 text",
        ) from exc

    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Playbook content is empty",
        )

    doc_key = safe_doc_key(filename)
    existing = session.scalar(
        select(Document).where(
            Document.tenant_id == tenant.tenant_id,
            Document.doc_key == doc_key,
        )
    )
    if existing is None:
        current_count = session.scalar(
            select(func.count()).select_from(Document).where(
                Document.tenant_id == tenant.tenant_id
            )
        ) or 0
        if int(current_count) >= max_count:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Playbook soft limit reached ({max_count})",
            )

    dest = tenant_playbook_path(tenant.tenant_id, doc_key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")

    try:
        document, chunk_count = ingest_playbook_markdown(
            session,
            tenant_id=tenant.tenant_id,
            content=content,
            doc_key=doc_key,
            path=str(dest),
            title=(title.strip() if title else None),
            commit=True,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding/ingest failed: {exc}",
        ) from exc

    return sanitize_output_payload(
        {
            "playbook": _document_payload(document, chunk_count),
            "message": "Playbook uploaded and indexed for this tenant only.",
        }
    )


@router.delete("/{document_id}")
def remove_playbook(
    document_id: uuid.UUID,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    ok = delete_playbook(
        session, tenant_id=tenant.tenant_id, document_id=document_id, commit=True
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook not found",
        )
    return sanitize_output_payload({"id": str(document_id), "deleted": True})
