"""Investigation API — LangGraph runs with auth + input guardrails (P5)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth import require_api_key
from api.app.config import get_settings
from opsmind.db.session import dispose_owner_engine, get_owner_session_factory
from opsmind.graph.runner import load_investigation_view, reset_graph_cache, run_investigation
from opsmind.guardrails.output import sanitize_output_payload

router = APIRouter(
    prefix="/investigations",
    tags=["investigations"],
    dependencies=[Depends(require_api_key)],
)


def get_owner_session() -> Iterator[Session]:
    settings = get_settings()
    factory = get_owner_session_factory(settings.database_url_sync)
    session = factory()
    try:
        yield session
    finally:
        session.close()


class CreateInvestigationBody(BaseModel):
    question: str = Field(min_length=3)
    wait: bool = Field(
        default=True,
        description="If true, run the graph to completion before responding.",
    )


@router.post("")
def create_and_run_investigation(body: CreateInvestigationBody) -> dict[str, Any]:
    settings = get_settings()
    if not body.wait:
        raise HTTPException(
            status_code=400,
            detail="Async enqueue is not enabled; set wait=true.",
        )
    try:
        result = run_investigation(question=body.question, settings=settings)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.get("status") == "guardrail_rejected":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "input_guardrail_rejected",
                "reason": (result.get("guardrail") or {}).get("reason")
                or "Input rejected by guardrails",
                "investigation_id": result.get("investigation_id"),
            },
        )

    factory = get_owner_session_factory(settings.database_url_sync)
    with factory() as session:
        view = load_investigation_view(session, uuid.UUID(result["investigation_id"]))
    view["run"] = {
        "node_trace": result.get("node_trace"),
        "finding_count": result.get("finding_count"),
        "errors": result.get("errors"),
        "retry_count": result.get("retry_count"),
    }
    return sanitize_output_payload(view)


@router.get("/{investigation_id}")
def get_investigation(
    investigation_id: uuid.UUID,
    session: Session = Depends(get_owner_session),
) -> dict[str, Any]:
    try:
        return load_investigation_view(session, investigation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def dispose_investigation_runtime() -> None:
    reset_graph_cache()
    dispose_owner_engine()
