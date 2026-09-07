"""Container entrypoint — host/port come only from environment."""

from __future__ import annotations

import os
import sys


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

    import uvicorn

    reload = os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    run_kwargs: dict = {"host": host, "port": port}
    if reload:
        run_kwargs["reload"] = True
        run_kwargs["reload_dirs"] = ["/app/apps", "/app/packages"]

    uvicorn.run("api.app.main:app", **run_kwargs)


if __name__ == "__main__":
    main()
