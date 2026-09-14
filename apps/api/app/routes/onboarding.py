"""Get-started status and one-click sample data for new workspaces."""

from __future__ import annotations

import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from api.app.auth import require_admin, require_tenant_context
from api.app.deps import get_tenant_session
from api.app.routes.data import SAMPLE_TEMPLATE_PATH, csv_soft_limits, run_csv_ingest
from api.app.routes.playbooks import (
    SAMPLE_PLAYBOOKS_ZIP,
    current_playbook_count,
    ingest_one_playbook,
    playbook_soft_limits,
)
from opsmind.db.ingest_csv import tenant_data_ready
from opsmind.db.memory_models import Investigation, Review
from opsmind.db.models import (
    Carrier,
    DailyMetric,
    InventorySnapshot,
    OrderItem,
    Product,
    Return,
    Shipment,
)
from opsmind.db.tenant_models import InviteCode, User
from opsmind.domain.tenant import TenantContext
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_PLAYBOOK_SUFFIXES = {".md", ".markdown", ".txt"}
# Fewer returns than this in a week isn't worth suggesting as an investigation.
_MIN_RETURNS_TO_SUGGEST = 3


@router.get("/status")
def onboarding_status(
    tenant: TenantContext = Depends(require_tenant_context),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Setup progress for the get-started checklist, plus questions worth asking
    about the workspace's own data."""
    tenant_id = tenant.tenant_id
    data = tenant_data_ready(session, tenant_id)
    playbooks = current_playbook_count(session, tenant_id)

    runs = session.scalar(
        select(func.count()).select_from(Investigation).where(Investigation.tenant_id == tenant_id)
    ) or 0
    latest_report_id = session.scalar(
        select(Investigation.id)
        .where(Investigation.tenant_id == tenant_id, Investigation.status == "completed")
        .order_by(Investigation.created_at.desc())
        .limit(1)
    )
    reviewed = session.scalar(select(Review.id).where(Review.tenant_id == tenant_id).limit(1)) is not None
    invites = session.scalar(
        select(func.count()).select_from(InviteCode).where(InviteCode.tenant_id == tenant_id)
    ) or 0
    members = session.scalar(
        select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    ) or 0
    first_day, last_day = session.execute(
        select(func.min(DailyMetric.metric_date), func.max(DailyMetric.metric_date)).where(
            DailyMetric.tenant_id == tenant_id
        )
    ).one()

    missing = [
        name for name, ok in (("business_data", data["ready"]), ("playbooks", playbooks > 0)) if not ok
    ]
    return sanitize_output_payload(
        {
            "is_admin": tenant.role == "admin",
            "ready_to_investigate": not missing,
            "missing": missing,
            "steps": {
                "business_data": {
                    "done": data["ready"],
                    "products": data["products"],
                    "orders": data["orders"],
                },
                "playbooks": {"done": playbooks > 0, "count": playbooks},
                "first_investigation": {
                    "done": latest_report_id is not None,
                    "count": int(runs),
                    "latest_id": str(latest_report_id) if latest_report_id else None,
                },
                "first_review": {"done": reviewed},
                "team": {"done": invites > 0 or members > 1, "invites": int(invites), "members": int(members)},
            },
            "data_coverage": (
                {"start": first_day.isoformat(), "end": last_day.isoformat()} if last_day else None
            ),
            "suggested_questions": (
                _suggested_questions(session, tenant_id, last_day) if data["ready"] and last_day else []
            ),
            "sample_data_available": SAMPLE_TEMPLATE_PATH.is_file() and SAMPLE_PLAYBOOKS_ZIP.is_file(),
        }
    )


def _suggested_questions(session: Session, tenant_id: UUID, last_day: date) -> list[dict[str, str]]:
    """Questions about the latest week of data, each phrased so the Planner
    resolves the same window (``week of <date>`` / ``between <a> and <b>``)."""
    start = last_day - timedelta(days=6)
    window = f"between {start.isoformat()} and {last_day.isoformat()}"
    suggestions: list[dict[str, str]] = []

    def revenue(first: date, last: date) -> float:
        total = session.scalar(
            select(func.coalesce(func.sum(DailyMetric.revenue), 0)).where(
                DailyMetric.tenant_id == tenant_id, DailyMetric.metric_date.between(first, last)
            )
        )
        return float(total or 0)

    current = revenue(start, last_day)
    prior = revenue(start - timedelta(days=7), start - timedelta(days=1))
    if prior > 0:
        change = (current - prior) / prior * 100
        suggestions.append(
            {
                "kind": "revenue",
                "title": f"Revenue {'down' if change < 0 else 'up'} {abs(change):.0f}% in the latest week",
                "question": (
                    f"Why did revenue {'decrease' if change < 0 else 'change'} in the week of "
                    f"{start.isoformat()} compared to the prior week?"
                ),
            }
        )

    zero_days = func.sum(case((InventorySnapshot.available <= 0, 1), else_=0))
    stockout = session.execute(
        select(Product.sku, Product.name, zero_days.label("zero_days"))
        .select_from(InventorySnapshot)
        .join(Product, Product.id == InventorySnapshot.product_id)
        .where(
            InventorySnapshot.tenant_id == tenant_id,
            InventorySnapshot.snapshot_date.between(start, last_day),
        )
        .group_by(Product.sku, Product.name)
        .having(zero_days > 0)
        .order_by(zero_days.desc())
        .limit(1)
    ).first()
    if stockout:
        suggestions.append(
            {
                "kind": "stockout",
                "title": f"{stockout.name} out of stock on {stockout.zero_days} day(s)",
                "question": f"Did {stockout.name} ({stockout.sku}) have a stockout {window}, and what should we do?",
            }
        )

    late = func.sum(case((Shipment.status == "delivered_late", 1), else_=0))
    carrier = session.execute(
        select(Carrier.name, late.label("late"), func.count().label("total"))
        .select_from(Shipment)
        .join(Carrier, Carrier.id == Shipment.carrier_id)
        .where(Shipment.tenant_id == tenant_id, Shipment.ship_date.between(start, last_day))
        .group_by(Carrier.name)
        .having(late > 0)
        .order_by(late.desc())
        .limit(1)
    ).first()
    if carrier:
        suggestions.append(
            {
                "kind": "carrier",
                "title": f"{carrier.name} delivered {carrier.late} of {carrier.total} shipments late",
                "question": f"Why were {carrier.name} deliveries late {window}, and what should we do?",
            }
        )

    returns = session.execute(
        select(Return.reason, Product.sku, Product.name, func.count().label("count"))
        .select_from(Return)
        .join(OrderItem, OrderItem.id == Return.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Return.tenant_id == tenant_id, Return.return_date.between(start, last_day))
        .group_by(Return.reason, Product.sku, Product.name)
        .order_by(func.count().desc())
        .limit(1)
    ).first()
    if returns and returns.count >= _MIN_RETURNS_TO_SUGGEST:
        suggestions.append(
            {
                "kind": "returns",
                "title": f"{returns.count} {returns.reason.replace('_', ' ')} returns for {returns.name}",
                "question": (
                    f"Why did returns spike for {returns.name} ({returns.sku}) with "
                    f"{returns.reason} reason codes {window}?"
                ),
            }
        )

    return suggestions


@router.post("/sample-data")
def load_sample_data(
    tenant: TenantContext = Depends(require_admin),
    session: Session = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Load the sample store (CSV bundle + SOP playbooks) in one step.

    Business data is loaded only into a workspace with none, and sample playbooks
    only when it has no playbooks — nothing a company uploaded is ever replaced.
    """
    if not SAMPLE_TEMPLATE_PATH.is_file() or not SAMPLE_PLAYBOOKS_ZIP.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample data isn't available on this deployment.",
        )
    tenant_id = tenant.tenant_id

    data = tenant_data_ready(session, tenant_id)
    loaded_business_data = False
    if data["products"] == 0 and data["orders"] == 0:
        run_csv_ingest(
            session,
            tenant=tenant,
            filename=SAMPLE_TEMPLATE_PATH.name,
            raw=SAMPLE_TEMPLATE_PATH.read_bytes(),
            max_rows=int(csv_soft_limits(session, tenant_id)["max_csv_rows"]),
        )
        loaded_business_data = True

    loaded_playbooks = 0
    if current_playbook_count(session, tenant_id) == 0:
        limits = playbook_soft_limits(session, tenant_id)
        doc_count = [0]
        with zipfile.ZipFile(SAMPLE_PLAYBOOKS_ZIP) as archive:
            for info in archive.infolist():
                name = Path(info.filename).name
                if info.is_dir() or name.startswith(".") or Path(name).suffix.lower() not in _PLAYBOOK_SUFFIXES:
                    continue
                result = ingest_one_playbook(
                    session,
                    tenant_id=tenant_id,
                    filename=name,
                    raw=archive.read(info),
                    title=None,
                    max_bytes=int(limits["max_playbook_upload_bytes"]),
                    max_count=int(limits["max_playbooks"]),
                    doc_count=doc_count,
                )
                loaded_playbooks += int(result["ok"])

    if loaded_business_data or loaded_playbooks:
        parts = (["sample business data"] if loaded_business_data else []) + (
            [f"{loaded_playbooks} sample playbooks"] if loaded_playbooks else []
        )
        message = f"Loaded {' and '.join(parts)}."
    else:
        message = "Your workspace already has business data and playbooks, so nothing was changed."

    return sanitize_output_payload(
        {
            "loaded": {"business_data": loaded_business_data, "playbooks": loaded_playbooks},
            "ready_to_investigate": tenant_data_ready(session, tenant_id)["ready"]
            and current_playbook_count(session, tenant_id) > 0,
            "message": message,
        }
    )
