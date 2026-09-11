"""Container entrypoint — host/port come only from environment."""

from __future__ import annotations

import os
import sys

# P2-16: arbitrary fixed key for a Postgres advisory lock guarding migrations —
# prevents multiple replicas starting simultaneously from racing `alembic upgrade`.
_MIGRATION_LOCK_KEY = 0x4F70734D696E64  # "OpsMind" as a rough numeric tag


def _run_migrations() -> None:
    """Run alembic upgrade head before starting the server.

    Also widens alembic_version.version_num to VARCHAR(128) when needed,
    because the default Alembic DDL only creates VARCHAR(32) which is too
    narrow for migration names longer than 32 characters.

    P2-16: migration failure is now FATAL (process exits non-zero) instead of
    printing a warning and starting the server against a possibly half-migrated
    schema. A Postgres advisory lock also serializes migrations across replicas
    that start concurrently.
    """
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

    engine = sqlalchemy.create_engine(
        db_url or alembic_cfg.get_main_option("sqlalchemy.url")
    )
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATION_LOCK_KEY})
            try:
                # Bug found by an actual fresh-DB end-to-end run: on a brand-new
                # database `alembic_version` doesn't exist yet, so the ALTER
                # below (which only handles an *existing* narrow column) is a
                # silent no-op — then Alembic creates the table itself with its
                # own default VARCHAR(32), and the run fails partway through the
                # very first upgrade once a revision id longer than 32 chars
                # shows up (0011_remove_warehouse_connections is 34 chars).
                # Pre-create the table at the right width so Alembic finds it
                # already there and never applies its narrow default.
                conn.execute(
                    sqlalchemy.text(
                        "CREATE TABLE IF NOT EXISTS alembic_version "
                        "(version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
                    )
                )
                conn.commit()

                # Also widen in place for a database that already has the table
                # at the old narrow width from a prior deployment.
                try:
                    conn.execute(
                        sqlalchemy.text(
                            "ALTER TABLE alembic_version "
                            "ALTER COLUMN version_num TYPE VARCHAR(128)"
                        )
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()  # already wide enough — fine

                command.upgrade(alembic_cfg, "head")
                print("[entrypoint] Alembic migrations applied.", flush=True)
            finally:
                conn.execute(sqlalchemy.text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK_KEY})
                conn.commit()
    finally:
        engine.dispose()


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

    # Apply any pending DB migrations before accepting traffic. Fatal on failure
    # (P2-16) — never serve traffic against a schema that failed to migrate.
    try:
        _run_migrations()
    except Exception as exc:
        print(f"[entrypoint] FATAL: migration step failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    import uvicorn

    reload = os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    run_kwargs: dict = {"host": host, "port": port}
    if reload:
        run_kwargs["reload"] = True
        run_kwargs["reload_dirs"] = ["/app/apps", "/app/packages"]

    uvicorn.run("api.app.main:app", **run_kwargs)


if __name__ == "__main__":
    main()
