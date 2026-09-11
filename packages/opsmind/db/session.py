"""Shared owner-DB session helpers (sync)."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def get_owner_engine(database_url_sync: str) -> Engine:
    global _engine, _factory
    if _engine is None:
        # P2-8: every route is `def` (not `async def`), so FastAPI runs them in a
        # threadpool of up to 40 by default; each request can open this session
        # plus the read-only session, and agent nodes open more. The previous
        # SQLAlchemy defaults (pool_size=5, max_overflow=10) exhaust under light
        # concurrent load. Size is configurable via env for deployment tuning.
        _engine = create_engine(
            database_url_sync,
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("DB_POOL_MAX_OVERFLOW", "20")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10")),
        )
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
