"""Warehouse connector API (MT6) — read-only Postgres DSN, admin-only."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth import require_admin, require_tenant_context
from api.app.deps import get_tenant_session
from opsmind.auth.secrets import build_postgres_dsn, encrypt_secret
from opsmind.db.warehouse import (
    connection_public_payload,
    get_warehouse_connection,
    probe_dsn,
)
from opsmind.db.tenant_models import WarehouseConnection
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


class WarehouseBody(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    schema_name: str = Field(default="public", min_length=1, max_length=64)


@router.get("")
def get_warehouse(
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    row = get_warehouse_connection(session, tenant.tenant_id)
    if row is None:
        return sanitize_output_payload({"connection": None})
    return sanitize_output_payload({"connection": connection_public_payload(row)})


@router.post("/test")
def test_warehouse(
    body: WarehouseBody,
    tenant: TenantContext = Depends(require_admin),
) -> dict[str, Any]:
    """Probe credentials without persisting."""
    _ = tenant  # auth only
    dsn = build_postgres_dsn(
        host=body.host.strip(),
        port=body.port,
        database=body.database.strip(),
        username=body.username.strip(),
        password=body.password,
    )
    result = probe_dsn(dsn, schema_name=body.schema_name.strip() or "public")
    return sanitize_output_payload(
        {
            "ok": result.ok,
            "missing_tables": result.missing_tables,
            "error": result.error,
        }
    )


@router.put("")
def upsert_warehouse(
    body: WarehouseBody,
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    dsn = build_postgres_dsn(
        host=body.host.strip(),
        port=body.port,
        database=body.database.strip(),
        username=body.username.strip(),
        password=body.password,
    )
    probe = probe_dsn(dsn, schema_name=body.schema_name.strip() or "public")
    ciphertext = encrypt_secret(dsn)

    row = get_warehouse_connection(session, tenant.tenant_id)
    if row is None:
        row = WarehouseConnection(
            id=uuid.uuid4(),
            tenant_id=tenant.tenant_id,
            created_by=tenant.user_id,
        )
        session.add(row)

    row.dialect = "postgresql"
    row.host = body.host.strip()
    row.port = body.port
    row.database = body.database.strip()
    row.username = body.username.strip()
    row.dsn_ciphertext = ciphertext
    row.schema_name = body.schema_name.strip() or "public"
    row.updated_at = datetime.now(timezone.utc)

    if probe.ok:
        row.status = "verified"
        row.last_verified_at = datetime.now(timezone.utc)
        row.last_error = None
    else:
        row.status = "failed"
        row.last_error = probe.error
        row.last_verified_at = None

    session.commit()
    session.refresh(row)

    if not probe.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "warehouse_probe_failed",
                "reason": probe.error,
                "missing_tables": probe.missing_tables,
                "connection": connection_public_payload(row),
            },
        )

    return sanitize_output_payload(
        {
            "connection": connection_public_payload(row),
            "message": "Warehouse connection verified. Investigations may use this data source.",
        }
    )


@router.delete("")
def delete_warehouse(
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    row = get_warehouse_connection(session, tenant.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No warehouse connection")
    session.delete(row)
    session.commit()
    return sanitize_output_payload({"deleted": True})
