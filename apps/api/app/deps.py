"""Shared FastAPI dependencies (MT1)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from api.app.auth import require_tenant_context
from api.app.config import get_settings
from opsmind.db.session import get_owner_session_factory
from opsmind.db.tenant_session import apply_tenant_session
from opsmind.domain.tenant import TenantContext


def get_tenant_session(
    tenant: TenantContext = Depends(require_tenant_context),
) -> Iterator[Session]:
    settings = get_settings()
    factory = get_owner_session_factory(settings.database_url_sync)
    session = factory()
    apply_tenant_session(session, tenant.tenant_id)
    try:
        yield session
    finally:
        session.close()
