"""Fill the DATABASE_URL* settings in .env from a Supabase connection string.

1. Supabase dashboard → Connect → "Session pooler" → copy the URI (port 5432).
   Not the Transaction pooler (port 6543): live updates need LISTEN/NOTIFY and
   per-session settings that transaction pooling drops.
2. Put it in .env:  SUPABASE_DB_URL=postgresql://postgres.<ref>:<password>@<host>:5432/postgres
3. From the repo root:  python scripts/configure_supabase_env.py

Writes DATABASE_URL (asyncpg), DATABASE_URL_SYNC (psycopg) and
DATABASE_URL_READONLY (the investigation SQL tool's read-only role), generates a
strong DB_READONLY_PASSWORD when none is set, and adds small connection pools.
Secrets are never printed. Safe to re-run.
"""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
TRANSACTION_POOLER_PORT = 6543
LEGACY_READONLY_PASSWORD = "opsmind_readonly"
POOL_DEFAULTS = {
    "DB_POOL_SIZE": "5",
    "DB_POOL_MAX_OVERFLOW": "5",
    "DB_READONLY_POOL_SIZE": "3",
    "DB_READONLY_POOL_MAX_OVERFLOW": "3",
}
_ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _mask(url: str) -> str:
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)


def main() -> int:
    if not ENV_PATH.is_file():
        return _fail(f"{ENV_PATH} not found — copy .env.example to .env first.")

    lines = ENV_PATH.read_text().splitlines()
    env: dict[str, str] = {}
    for line in lines:
        match = _ENV_LINE.match(line)
        if match:
            env[match.group(1)] = match.group(2).strip()

    raw = env.get("SUPABASE_DB_URL", "").strip().strip("'\"")
    if not raw:
        return _fail("add SUPABASE_DB_URL=<Session pooler URI> to .env first.")

    parts = urlsplit(raw)
    if parts.scheme not in {"postgres", "postgresql"}:
        return _fail("SUPABASE_DB_URL must start with postgresql://")
    if not parts.hostname or not parts.username or parts.password is None:
        return _fail("SUPABASE_DB_URL must include the user, password and host.")
    if (parts.port or 5432) == TRANSACTION_POOLER_PORT:
        return _fail(
            "that is the Transaction pooler (port 6543). Copy the Session pooler URI "
            "(port 5432) instead — live updates need LISTEN/NOTIFY."
        )

    # Keep the user/password exactly as given (already percent-encoded in the URI).
    userinfo, _, hostport = parts.netloc.rpartition("@")
    user, _, password = userinfo.partition(":")
    database = parts.path.lstrip("/") or "postgres"

    # Session pooler logins are "<role>.<project-ref>"; every role we connect as
    # needs the same suffix to be routed to this project.
    ref_suffix = ""
    if parts.hostname.endswith("pooler.supabase.com") and "." in user:
        ref_suffix = "." + user.split(".", 1)[1]

    readonly_user = env.get("DB_READONLY_USER") or "opsmind_readonly"
    readonly_password = env.get("DB_READONLY_PASSWORD", "")
    generated = readonly_password in {"", LEGACY_READONLY_PASSWORD}
    if generated:
        readonly_password = secrets.token_urlsafe(24)

    target = f"{hostport}/{database}"
    updates = {
        "DATABASE_URL": f"postgresql+asyncpg://{user}:{password}@{target}?ssl=require",
        "DATABASE_URL_SYNC": f"postgresql://{user}:{password}@{target}?sslmode=require",
        # The SQL tool swaps this prefix for a synchronous driver, hence sslmode.
        "DATABASE_URL_READONLY": (
            f"postgresql+asyncpg://{readonly_user}{ref_suffix}:{readonly_password}"
            f"@{target}?sslmode=require"
        ),
        "DB_READONLY_USER": readonly_user,
        "DB_READONLY_PASSWORD": readonly_password,
    }
    for key, value in POOL_DEFAULTS.items():
        if not env.get(key):
            updates[key] = value

    written: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = _ENV_LINE.match(line)
        if match and match.group(1) in updates:
            output.append(f"{match.group(1)}={updates[match.group(1)]}")
            written.add(match.group(1))
        else:
            output.append(line)
    missing = [key for key in updates if key not in written]
    if missing:
        output += ["", "# Added by scripts/configure_supabase_env.py"]
        output += [f"{key}={updates[key]}" for key in missing]
    ENV_PATH.write_text("\n".join(output) + "\n")

    print(f"Updated {ENV_PATH}")
    for key in ("DATABASE_URL", "DATABASE_URL_SYNC", "DATABASE_URL_READONLY"):
        print(f"  {key}={_mask(updates[key])}")
    if generated:
        print("  DB_READONLY_PASSWORD=<generated>")
    print("Next: alembic upgrade head, then python -m opsmind.db.seed (see README → Quick Start).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
