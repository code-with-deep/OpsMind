"""CSV business-data upload + ready status (MT4)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.auth import require_admin, require_tenant_context
from api.app.config import get_settings
from api.app.deps import get_tenant_session
from opsmind.db.ingest_csv import (
    CsvIngestError,
    extract_csv_bundle,
    ingest_csv_tables,
    tenant_data_ready,
)
from opsmind.db.tenant_models import IngestJob, TenantSettings
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/data", tags=["data"])

DEFAULT_UPLOADS = Path(__file__).resolve().parents[4] / "data" / "uploads"


def _soft_limits(session: Session, tenant_id: uuid.UUID) -> dict[str, Any]:
    settings = get_settings()
    row = session.get(TenantSettings, tenant_id)
    limits = dict(row.soft_limits or {}) if row else {}
    limits.setdefault("max_csv_upload_bytes", settings.csv_max_upload_mb * 1024 * 1024)
    limits.setdefault("max_csv_rows", settings.csv_max_rows)
    return limits


def _job_payload(job: IngestJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "filename": job.filename,
        "status": job.status,
        "row_counts": job.row_counts or {},
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/ready")
def data_ready(
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    status_payload = tenant_data_ready(session, tenant.tenant_id)
    return sanitize_output_payload(status_payload)


@router.get("/ingest-jobs")
def list_ingest_jobs(
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    jobs = session.scalars(
        select(IngestJob)
        .where(IngestJob.tenant_id == tenant.tenant_id)
        .order_by(IngestJob.created_at.desc())
        .limit(50)
    ).all()
    items = [_job_payload(j) for j in jobs]
    return sanitize_output_payload({"jobs": items, "count": len(items)})


@router.post("/csv")
async def upload_csv_bundle(
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    filename = file.filename or "data.zip"
    limits = _soft_limits(session, tenant.tenant_id)
    max_bytes = int(limits["max_csv_upload_bytes"])
    max_rows = int(limits["max_csv_rows"])

    raw = await file.read()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"CSV upload exceeds soft limit of {max_bytes} bytes",
        )

    job = IngestJob(
        id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        kind="csv",
        filename=filename,
        status="processing",
        row_counts={},
        created_by=tenant.user_id,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    dest_dir = Path(
        str(DEFAULT_UPLOADS / str(tenant.tenant_id) / "csv")
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{job.id}_{Path(filename).name}"
    dest.write_bytes(raw)

    try:
        files = extract_csv_bundle(raw, filename)
        result = ingest_csv_tables(
            session,
            tenant_id=tenant.tenant_id,
            files=files,
            max_rows=max_rows,
            replace=True,
        )
        job.status = "done"
        job.row_counts = result.row_counts
        job.error = None
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(job)
    except CsvIngestError as exc:
        session.rollback()
        # re-attach job after rollback
        job = session.get(IngestJob, job.id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(job)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        job = session.get(IngestJob, job.id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CSV ingest failed: {exc}",
        ) from exc

    ready = tenant_data_ready(session, tenant.tenant_id)
    return sanitize_output_payload(
        {
            "job": _job_payload(job),
            "ready": ready,
            "message": "Business data replaced for this tenant and daily_metrics derived.",
        }
    )
