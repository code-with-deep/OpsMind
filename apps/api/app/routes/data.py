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
from opsmind.db.models import (
    Campaign,
    Carrier,
    DailyMetric,
    InventorySnapshot,
    Order,
    OrderItem,
    Product,
    Return,
    Shipment,
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


@router.delete("/ingest-jobs/{job_id}")
def delete_ingest_job(
    job_id: uuid.UUID,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Delete a single ingest job record and its uploaded ZIP file.

    If this was the last completed job, also wipes all ingested business data
    so the ready-gate resets and the admin must re-upload.
    """
    job = session.get(IngestJob, job_id)
    if job is None or job.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Remove the uploaded ZIP from disk (best-effort)
    upload_dir = DEFAULT_UPLOADS / str(tenant.tenant_id) / "csv"
    if job.filename and upload_dir.exists():
        import glob as _glob
        for f in _glob.glob(str(upload_dir / f"*_{job.filename}")):
            try:
                Path(f).unlink()
            except Exception:  # noqa: BLE001
                pass

    # Delete the job record
    session.delete(job)
    session.flush()

    # If no other "done" jobs remain, wipe the business tables so ready resets
    remaining_done = session.scalars(
        select(IngestJob).where(
            IngestJob.tenant_id == tenant.tenant_id,
            IngestJob.status == "done",
        )
    ).all()

    wiped = False
    if not remaining_done:
        for model in [
            Return, Shipment, InventorySnapshot, OrderItem,
            Order, Campaign, Carrier, Product, DailyMetric,
        ]:
            rows = session.scalars(
                select(model).where(model.tenant_id == tenant.tenant_id)  # type: ignore[attr-defined]
            ).all()
            for row in rows:
                session.delete(row)
        wiped = True

    session.commit()
    ready = tenant_data_ready(session, tenant.tenant_id)
    return sanitize_output_payload({
        "deleted": True,
        "wiped_business_data": wiped,
        "ready": ready["ready"],
        "message": "Job deleted. Business data also cleared — upload a new ZIP to re-enable investigations." if wiped else "Job deleted.",
    })


@router.delete("/csv")
def delete_csv_data(
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Delete all business data for this tenant (admin only).

    Wipes products, orders, order_items, shipments, returns, inventory,
    carriers, campaigns, daily_metrics, and ingest_jobs — resets the
    ready-gate so the admin can re-upload a corrected dataset.
    """
    tid = tenant.tenant_id

    # Delete in FK-safe order (children before parents)
    deleted: dict[str, int] = {}
    for model, label in [
        (Return, "returns"),
        (Shipment, "shipments"),
        (InventorySnapshot, "inventory_snapshots"),
        (OrderItem, "order_items"),
        (Order, "orders"),
        (Campaign, "campaigns"),
        (Carrier, "carriers"),
        (Product, "products"),
        (DailyMetric, "daily_metrics"),
        (IngestJob, "ingest_jobs"),
    ]:
        rows = session.scalars(
            select(model).where(model.tenant_id == tid)  # type: ignore[attr-defined]
        ).all()
        for row in rows:
            session.delete(row)
        deleted[label] = len(rows)

    session.commit()

    # Also remove uploaded ZIP files from disk (best-effort, non-fatal)
    upload_dir = DEFAULT_UPLOADS / str(tid) / "csv"
    if upload_dir.exists():
        import shutil
        try:
            shutil.rmtree(upload_dir)
        except Exception:  # noqa: BLE001
            pass

    return sanitize_output_payload(
        {
            "deleted": deleted,
            "ready": False,
            "message": "All business data deleted. Upload a new CSV ZIP to re-enable investigations.",
        }
    )
