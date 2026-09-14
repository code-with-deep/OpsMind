"""Backend entrypoint: apply database migrations, then serve the API.

Run from the repository root (settings are read from ./.env):

    python -m api.entrypoint                     # serve on API_HOST:API_PORT
    UVICORN_RELOAD=1 python -m api.entrypoint    # auto-reload while developing
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# P2-16: fixed key for a Postgres advisory lock guarding migrations — prevents
# several API processes starting at once from racing `alembic upgrade`.
_MIGRATION_LOCK_KEY = 0x4F70734D696E64  # "OpsMind" as a rough numeric tag


def _run_migrations(database_url_sync: str) -> None:
    """Run `alembic upgrade head` under an advisory lock.

    P2-16: failure is fatal — never serve traffic against a schema that failed
    to migrate. alembic/env.py reads the URL from the environment and widens
    alembic_version for our long revision ids.
    """
    import sqlalchemy
    from alembic import command
    from alembic.config import Config

    os.environ.setdefault("DATABASE_URL_SYNC", database_url_sync)
    alembic_cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_REPO_ROOT / "packages/opsmind/db/alembic"))

    engine = sqlalchemy.create_engine(database_url_sync)
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY})
            conn.commit()
            try:
                command.upgrade(alembic_cfg, "head")
                print("[entrypoint] Alembic migrations applied.", flush=True)
            finally:
                conn.execute(
                    sqlalchemy.text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK_KEY}
                )
                conn.commit()
    finally:
        engine.dispose()


def main() -> None:
    from dotenv import load_dotenv
    from pydantic import ValidationError

    from api.app.config import get_settings

    # Export .env into the process environment (already-set variables win) so
    # modules reading os.environ — pool sizes, read-only role, the reload worker —
    # see the same configuration as Settings.
    load_dotenv(_REPO_ROOT / ".env", override=False)

    try:
        settings = get_settings()
    except ValidationError as exc:
        # Name the fields only — the full error would echo configured secrets.
        fields = sorted({".".join(str(p) for p in err["loc"]).upper() for err in exc.errors()})
        print(f"[entrypoint] Missing or invalid settings in .env: {', '.join(fields)}", file=sys.stderr)
        sys.exit(1)

    try:
        _run_migrations(settings.database_url_sync)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] FATAL: migration step failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    import uvicorn

    reload = os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    # Long-lived /events/stream connections would otherwise block shutdown/reload.
    run_kwargs: dict = {
        "host": settings.api_host,
        "port": settings.api_port,
        "timeout_graceful_shutdown": 5,
    }
    if reload:
        run_kwargs["reload"] = True
        run_kwargs["reload_dirs"] = [str(_REPO_ROOT / "apps"), str(_REPO_ROOT / "packages")]

    uvicorn.run("api.app.main:app", **run_kwargs)


if __name__ == "__main__":
    main()
