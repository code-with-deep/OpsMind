"""Playbook upload / list / delete (MT3)."""

from __future__ import annotations

import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
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
_ZIP_SUFFIXES = {".zip"}
# Zip-bomb guard: cap total decompressed content, independent of the raw ZIP
# size check below. Plain-text SOPs don't realistically compress beyond ~20x.
_ZIP_DECOMPRESSED_RATIO_CAP = 20

SAMPLE_PLAYBOOKS_ZIP = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "sample_templates"
    / "opsmind_sample_playbooks.zip"
)


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


@router.get("/sample-template")
def download_sample_playbooks(
    tenant: TenantContext = Depends(require_tenant_context),
) -> FileResponse:
    """Download the sample SOP playbooks (5 .md files, zipped) tuned to the
    planted scenario in the sample CSV bundle (GET /data/sample-template) —
    upload the CSV data first, then these, for grounded playbook citations.
    Upload the ZIP as-is via "Upload SOP(s)" — POST /playbooks extracts and
    ingests every .md/.markdown/.txt file inside a ZIP automatically.
    """
    if not SAMPLE_PLAYBOOKS_ZIP.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample playbooks are not available on this deployment.",
        )
    return FileResponse(
        SAMPLE_PLAYBOOKS_ZIP,
        media_type="application/zip",
        filename="opsmind_sample_playbooks.zip",
    )


def _current_playbook_count(session: Session, tenant_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id)
        )
        or 0
    )


def _ingest_one_playbook(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    filename: str,
    raw: bytes,
    title: str | None,
    max_bytes: int,
    max_count: int,
    doc_count: list[int],
) -> dict[str, Any]:
    """Ingest one playbook file's bytes. Returns a per-file result dict —
    never raises, so one bad file in a ZIP batch doesn't abort the rest.
    `doc_count` is a 1-item mutable list used as an in-out counter across
    calls in the same batch (avoids an extra COUNT query per file).
    """
    if len(raw) > max_bytes:
        return {"filename": filename, "ok": False, "error": f"exceeds soft limit of {max_bytes} bytes"}
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"filename": filename, "ok": False, "error": "must be UTF-8 text"}
    if not content.strip():
        return {"filename": filename, "ok": False, "error": "content is empty"}

    doc_key = safe_doc_key(filename)
    existing = session.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.doc_key == doc_key)
    )
    if existing is None and doc_count[0] >= max_count:
        return {"filename": filename, "ok": False, "error": f"playbook soft limit reached ({max_count})"}

    dest = tenant_playbook_path(tenant_id, doc_key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")

    try:
        document, chunk_count = ingest_playbook_markdown(
            session,
            tenant_id=tenant_id,
            content=content,
            doc_key=doc_key,
            path=str(dest),
            title=(title.strip() if title else None),
            commit=True,
        )
    except ValueError as exc:
        return {"filename": filename, "ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"filename": filename, "ok": False, "error": f"embedding/ingest failed: {exc}"}

    if existing is None:
        doc_count[0] += 1
    return {"filename": filename, "ok": True, "playbook": _document_payload(document, chunk_count)}


@router.post("")
async def upload_playbook(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    filename = file.filename or "playbook.md"
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in _ALLOWED_SUFFIXES and suffix not in _ZIP_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Markdown (.md), plain text (.txt), or a .zip of those files is supported",
        )

    limits = _soft_limits(session, tenant.tenant_id)
    max_bytes = int(limits["max_playbook_upload_bytes"])
    max_count = int(limits["max_playbooks"])

    # P0-7: Check Content-Length header before reading entire body into RAM.
    content_length = file.headers.get("content-length")
    if content_length:
        try:
            content_length_int = int(content_length)
            if content_length_int > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds soft limit of {max_bytes} bytes",
                )
        except ValueError:
            pass  # Invalid header, continue with byte-checking below

    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload exceeds soft limit of {max_bytes} bytes",
        )

    doc_count = [_current_playbook_count(session, tenant.tenant_id)]

    if suffix in _ZIP_SUFFIXES:
        try:
            zf = zipfile.ZipFile(BytesIO(raw))
        except zipfile.BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ZIP archive",
            ) from exc

        entries = [
            info
            for info in zf.infolist()
            if not info.is_dir()
            and Path(info.filename).suffix.lower() in _ALLOWED_SUFFIXES
            and not Path(info.filename).name.startswith(".")
        ]
        if not entries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ZIP contains no .md/.markdown/.txt files",
            )

        # Zip-bomb guard: bound total decompressed size independent of the
        # already-checked compressed size (P0-7 spirit — never trust the
        # archive's own size metadata blindly, but info.file_size here is
        # cheap to sum before any decompression happens).
        total_decompressed = sum(info.file_size for info in entries)
        if total_decompressed > max_bytes * _ZIP_DECOMPRESSED_RATIO_CAP:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="ZIP decompresses far beyond the playbook size limit — rejected.",
            )

        results = [
            _ingest_one_playbook(
                session,
                tenant_id=tenant.tenant_id,
                filename=Path(info.filename).name,
                raw=zf.read(info),
                title=None,  # per-file titles come from each file's own heading
                max_bytes=max_bytes,
                max_count=max_count,
                doc_count=doc_count,
            )
            for info in entries
        ]
        ok_count = sum(1 for r in results if r["ok"])
        return sanitize_output_payload(
            {
                "playbooks": [r["playbook"] for r in results if r["ok"]],
                "errors": [
                    {"filename": r["filename"], "error": r["error"]} for r in results if not r["ok"]
                ],
                "count": ok_count,
                "message": f"{ok_count}/{len(results)} playbooks uploaded and indexed for this tenant only.",
            }
        )

    result = _ingest_one_playbook(
        session,
        tenant_id=tenant.tenant_id,
        filename=filename,
        raw=raw,
        title=title,
        max_bytes=max_bytes,
        max_count=max_count,
        doc_count=doc_count,
    )
    if not result["ok"]:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if "soft limit" in result["error"]
            else status.HTTP_502_BAD_GATEWAY
            if "embedding" in result["error"]
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=result["error"])

    return sanitize_output_payload(
        {
            "playbook": result["playbook"],
            "playbooks": [result["playbook"]],
            "count": 1,
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
