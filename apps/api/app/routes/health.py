from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.app.config import get_settings
from api.app.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: process is up. Does not check dependencies."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
    }


@router.get("/ready")
async def ready() -> JSONResponse:
    """Readiness: process can serve traffic (DB reachable)."""
    db_ok = await check_database()
    payload = {
        "status": "ready" if db_ok else "not_ready",
        "checks": {
            "database": "ok" if db_ok else "unavailable",
        },
    }
    return JSONResponse(content=payload, status_code=200 if db_ok else 503)
