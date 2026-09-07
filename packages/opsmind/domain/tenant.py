"""Tenant context derived from authentication (MT1/MT2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Resolved tenant for the current request — never trust client-sent tenant ids."""

    tenant_id: uuid.UUID
    tenant_slug: str
    tenant_name: str
    api_key_id: uuid.UUID | None = None
    api_key_prefix: str | None = None
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    role: str | None = None
    auth_method: str = "api_key"
