from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.config import get_settings
from api.app.db import dispose_engine
from api.app.routes.auth import router as auth_router
from api.app.routes.health import router as health_router
from api.app.routes.investigations import (
    dispose_investigation_runtime,
    router as investigations_router,
)
from api.app.routes.data import router as data_router
from api.app.routes.playbooks import router as playbooks_router
from api.app.routes.warehouse import router as warehouse_router
from api.app.routes.tools import dispose_tool_engines, router as tools_router


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
    if settings.opsmind_secrets_key:
        os.environ["OPSMIND_SECRETS_KEY"] = settings.opsmind_secrets_key
    if settings.jwt_secret:
        os.environ.setdefault("JWT_SECRET", settings.jwt_secret)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _sync_embedding_env()
    yield
    dispose_investigation_runtime()
    dispose_tool_engines()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    _sync_embedding_env()
    app = FastAPI(
        title=settings.app_name,
        description="Self-Correcting Multi-Agent Operations Intelligence System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Enable CORS for the frontend console (localhost:3000 and any operator host)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(playbooks_router)
    app.include_router(data_router)
    app.include_router(warehouse_router)
    app.include_router(tools_router)
    app.include_router(investigations_router)

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
            "warehouse": "/warehouse",
            "tools": "/tools/sql/templates",
            "investigations": "/investigations",
        }

    return app


app = create_app()
