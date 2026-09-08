"""Container entrypoint — host/port come only from environment."""

from __future__ import annotations

import os
import sys


def _run_migrations() -> None:
    """Run alembic upgrade head before starting the server.

    Also widens alembic_version.version_num to VARCHAR(128) when needed,
    because the default Alembic DDL only creates VARCHAR(32) which is too
    narrow for migration names longer than 32 characters.
    """
    try:
        import sqlalchemy
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("/app/alembic.ini")

        # Resolve sync DB URL (Alembic needs a non-async driver)
        db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get(
            "DATABASE_URL_SYNC_DOCKER"
        )
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        # Widen version_num column if the DB is already initialised but narrow
        try:
            engine = sqlalchemy.create_engine(
                db_url or alembic_cfg.get_main_option("sqlalchemy.url")
            )
            with engine.connect() as conn:
                conn.execute(
                    sqlalchemy.text(
                        "ALTER TABLE alembic_version "
                        "ALTER COLUMN version_num TYPE VARCHAR(128)"
                    )
                )
                conn.commit()
            engine.dispose()
        except Exception:
            pass  # table doesn't exist yet, or already wide enough — fine

        command.upgrade(alembic_cfg, "head")
        print("[entrypoint] Alembic migrations applied.", flush=True)
    except Exception as exc:
        print(
            f"[entrypoint] WARNING: migration step failed: {exc}",
            file=sys.stderr,
            flush=True,
        )


def main() -> None:
    host = os.environ.get("API_HOST")
    port_raw = os.environ.get("API_PORT")
    if not host or not port_raw:
        print("API_HOST and API_PORT must be set via environment /.env", file=sys.stderr)
        sys.exit(1)

    try:
        port = int(port_raw)
    except ValueError:
        print(f"API_PORT must be an integer, got: {port_raw!r}", file=sys.stderr)
        sys.exit(1)

    # Apply any pending DB migrations before accepting traffic
    _run_migrations()

    import uvicorn

    reload = os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    run_kwargs: dict = {"host": host, "port": port}
    if reload:
        run_kwargs["reload"] = True
        run_kwargs["reload_dirs"] = ["/app/apps", "/app/packages"]

    uvicorn.run("api.app.main:app", **run_kwargs)


if __name__ == "__main__":
    main()
