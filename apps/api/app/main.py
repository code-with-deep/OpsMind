from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.app.config import get_settings
from api.app.db import dispose_engine
from api.app.realtime import broker
from api.app.routes.access import router as access_router
from api.app.routes.auth import router as auth_router
from api.app.routes.health import router as health_router
from api.app.routes.investigations import (
    dispose_investigation_runtime,
    router as investigations_router,
)
from api.app.routes.data import router as data_router
from api.app.routes.events import router as events_router
from api.app.routes.notifications import router as notifications_router
from api.app.routes.onboarding import router as onboarding_router
from api.app.routes.playbooks import router as playbooks_router
from api.app.routes.tools import dispose_tool_engines, router as tools_router
from opsmind.graph.runner import fail_interrupted_investigations

logger = logging.getLogger("opsmind.api")

_FIELD_LABELS = {
    "email": "Email",
    "password": "Password",
    "current_password": "Current password",
    "new_password": "New password",
    "company_name": "Company name",
    "name": "Company name",
    "invite_code": "Invite code",
    "question": "Question",
    "notes": "Notes",
    "reason": "Reason",
}


def _friendly_validation_message(err: dict) -> tuple[str, str]:
    """Turn one pydantic error into (field, sentence a non-developer understands)."""
    loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
    field = loc[-1] if loc else ""
    label = _FIELD_LABELS.get(field, field.replace("_", " ").capitalize() or "Request")
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    raw = str(err.get("msg", ""))

    if kind == "missing":
        return field, f"{label} is required."
    if field == "email" and kind in {"value_error", "string_type"}:
        return field, "Please enter a valid email address, like name@company.com."
    if field == "token":
        return field, "This reset link is invalid or incomplete. Request a new one."
    if kind == "string_too_short":
        minimum = ctx.get("min_length")
        if minimum in (None, 1):
            return field, f"{label} is required."
        return field, f"{label} must be at least {minimum} characters."
    if kind == "string_too_long":
        return field, f"{label} must be at most {ctx.get('max_length')} characters."
    if kind == "value_error":
        # Custom validators raise ValueError("<sentence>"); pydantic prefixes it.
        return field, raw.removeprefix("Value error, ")
    if kind in {"json_invalid", "model_attributes_type", "dict_type"}:
        return field, "The request was malformed. Please refresh the page and try again."
    return field, f"{label}: {raw}"


async def _validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": field, "message": message}
        for field, message in (_friendly_validation_message(e) for e in exc.errors())
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": errors[0]["message"] if errors else "Invalid request.", "errors": errors},
    )


def _recover_interrupted_runs() -> None:
    try:
        count = fail_interrupted_investigations(get_settings())
    except Exception:  # noqa: BLE001 — DB may be unavailable (tests, cold start)
        logger.warning("Skipped interrupted-investigation recovery", exc_info=True)
        return
    if count:
        logger.warning("Marked %d interrupted investigation(s) as failed", count)


def _configure_logging(settings) -> None:
    """P2-17: LOG_LEVEL was a required Settings field that nothing ever read.
    Wire it up to stdlib logging so the warnings/exceptions added throughout
    the agents and routes (LLM fallbacks, internal errors, rate limits) are
    actually emitted somewhere.
    """
    level_name = (settings.log_level or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Quiet noisy third-party loggers at INFO unless explicitly debugging.
    if level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def _validate_secrets(settings) -> None:
    """P0-6: Refuse to start if secrets are weak or use known placeholders.

    Gated on APP_ENV: "development" and "test" are exempt (short/placeholder
    values are fine for local dev and the test suite, which sets its own short
    fixture keys like "test-opsmind-api-key"). Any other APP_ENV value —
    staging, production, anything a real deployment would use — is treated as
    production-like and enforced strictly.
    """
    app_env = (settings.app_env or "").strip().lower()
    if app_env in {"development", "dev", "test", "testing"}:
        return

    KNOWN_PLACEHOLDERS = {
        "change-me-opsmind-jwt-secret-dev-only",
        "change-me-opsmind-dev-key",
    }

    if settings.jwt_secret in KNOWN_PLACEHOLDERS or len(settings.jwt_secret) < 32:
        raise ValueError(
            f"JWT_SECRET must be a strong secret (≥32 chars), not the default placeholder. "
            f"Got: {settings.jwt_secret[:20]}... (len={len(settings.jwt_secret)}). "
            f"APP_ENV={app_env!r} — set APP_ENV=development to bypass this check locally."
        )

    if settings.opsmind_api_key in KNOWN_PLACEHOLDERS or len(settings.opsmind_api_key) < 24:
        raise ValueError(
            f"OPSMIND_API_KEY must be set explicitly (≥24 chars), not the default placeholder. "
            f"Got: {settings.opsmind_api_key[:20]}... (len={len(settings.opsmind_api_key)}). "
            f"APP_ENV={app_env!r} — set APP_ENV=development to bypass this check locally."
        )


def _sync_embedding_env() -> None:
    """Mirror Settings into process env for shared opsmind.tools.embeddings helpers."""
    settings = get_settings()
    os.environ["OPSMIND_EMBEDDING_PROVIDER"] = (
        settings.opsmind_embedding_provider or "local"
    ).strip().lower()
    os.environ["OPSMIND_EMBEDDING_MODEL"] = (
        settings.opsmind_embedding_model or "text-embedding-3-small"
    )
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openai_api_base:
        os.environ["OPENAI_API_BASE"] = settings.openai_api_base
    if settings.jwt_secret:
        os.environ.setdefault("JWT_SECRET", settings.jwt_secret)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _sync_embedding_env()
    _recover_interrupted_runs()
    yield
    broker.stop()
    dispose_investigation_runtime()
    dispose_tool_engines()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings)
    _validate_secrets(settings)  # P0-6: Fail fast on weak secrets
    _sync_embedding_env()
    app = FastAPI(
        title=settings.app_name,
        description="Self-Correcting Multi-Agent Operations Intelligence System",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_exception_handler(RequestValidationError, _validation_error_handler)

    # P1-11: CORS must not combine allow_origins=["*"] with allow_credentials=True
    # (invalid per the CORS spec, and it lets any page make authenticated
    # cross-origin requests). Restrict to an explicit allowlist.
    configured_origins = [
        o.strip() for o in (settings.cors_allowed_origins or "").split(",") if o.strip()
    ]
    allowed_origins = configured_origins or [settings.app_public_url]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(access_router)
    app.include_router(notifications_router)
    app.include_router(onboarding_router)
    app.include_router(playbooks_router)
    app.include_router(data_router)
    app.include_router(tools_router)
    app.include_router(investigations_router)
    app.include_router(events_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": "/health",
            "ready": "/ready",
            "auth": "/auth/signup",
            "playbooks": "/playbooks",
            "data": "/data/csv",
            "tools": "/tools/sql/templates",
            "investigations": "/investigations",
        }

    return app


app = create_app()
