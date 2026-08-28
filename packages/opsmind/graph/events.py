"""Write investigation_events for each agent/node transition."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from opsmind.db.memory_models import Investigation, InvestigationEvent


def write_event(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        InvestigationEvent(
            id=uuid.uuid4(),
            investigation_id=investigation_id,
            event_type=event_type,
            payload=payload or {},
        )
    )
    session.commit()


def update_investigation(
    session: Session,
    *,
    investigation_id: uuid.UUID,
    **fields: Any,
) -> Investigation | None:
    from datetime import date as date_cls

    inv = session.get(Investigation, investigation_id)
    if inv is None:
        return None
    for key, value in fields.items():
        if not hasattr(inv, key):
            continue
        if key in {"window_start", "window_end"} and isinstance(value, str):
            value = date_cls.fromisoformat(value)
        setattr(inv, key, value)
    session.commit()
    session.refresh(inv)
    return inv
