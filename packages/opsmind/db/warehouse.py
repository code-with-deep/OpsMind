"""Warehouse connection probe + engine resolution (MT6)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from opsmind.auth.secrets import decrypt_secret
from opsmind.db.tenant_models import WarehouseConnection
from opsmind.tools.sql_templates import ALLOWLISTED_TABLES


@dataclass
class WarehouseProbeResult:
    ok: bool
    missing_tables: list[str]
    error: str | None = None


def get_warehouse_connection(
    session: Session, tenant_id: uuid.UUID
) -> WarehouseConnection | None:
    return session.scalar(
        select(WarehouseConnection).where(WarehouseConnection.tenant_id == tenant_id)
    )


def warehouse_verified(session: Session, tenant_id: uuid.UUID) -> bool:
    row = get_warehouse_connection(session, tenant_id)
    return row is not None and row.status == "verified"


def probe_dsn(dsn: str, *, schema_name: str = "public") -> WarehouseProbeResult:
    """Connect and confirm allowlisted ecommerce tables exist (read-only probe)."""
    url = dsn.replace("postgresql+asyncpg://", "postgresql://")
    engine: Engine | None = None
    try:
        engine = create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
        missing: list[str] = []
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            for table in sorted(ALLOWLISTED_TABLES):
                # schema-qualified existence check
                exists = conn.execute(
                    text("SELECT to_regclass(:qname)"),
                    {"qname": f"{schema_name}.{table}"},
                ).scalar()
                if not exists:
                    missing.append(table)
        if missing:
            return WarehouseProbeResult(
                ok=False,
                missing_tables=missing,
                error=f"Missing required tables: {', '.join(missing)}",
            )
        return WarehouseProbeResult(ok=True, missing_tables=[])
    except Exception as exc:  # noqa: BLE001
        return WarehouseProbeResult(ok=False, missing_tables=[], error=str(exc)[:500])
    finally:
        if engine is not None:
            engine.dispose()


def connection_public_payload(row: WarehouseConnection) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "dialect": row.dialect,
        "host": row.host,
        "port": row.port,
        "database": row.database,
        "username": row.username,
        "schema_name": row.schema_name,
        "status": row.status,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def resolve_sql_target(
    owner_session: Session,
    *,
    tenant_id: uuid.UUID,
    fallback_database_url_readonly: str,
) -> tuple[str, bool]:
    """Return (sync_dsn, is_external_warehouse).

    - No connection row → shared OpsMind readonly URL (CSV path).
    - Connection exists but not verified → fail closed (raise).
    - Verified → decrypted warehouse DSN.
    """
    row = get_warehouse_connection(owner_session, tenant_id)
    if row is None:
        return fallback_database_url_readonly, False
    if row.status != "verified":
        raise ValueError(
            "Warehouse connection exists but is not verified — "
            "fix the connection in Settings or delete it to use CSV data."
        )
    return decrypt_secret(row.dsn_ciphertext), True
