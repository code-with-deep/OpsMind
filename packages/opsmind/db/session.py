"""Shared owner-DB session helpers (sync)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def get_owner_engine(database_url_sync: str) -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = create_engine(database_url_sync, pool_pre_ping=True)
        _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_owner_session_factory(database_url_sync: str) -> sessionmaker[Session]:
    get_owner_engine(database_url_sync)
    assert _factory is not None
    return _factory


def dispose_owner_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _factory = None
