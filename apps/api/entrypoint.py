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

    uvicorn.run("api.app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
