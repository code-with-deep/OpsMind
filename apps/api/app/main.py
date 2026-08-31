from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.config import get_settings
from api.app.db import dispose_engine
from api.app.routes.health import router as health_router
from api.app.routes.investigations import (
    dispose_investigation_runtime,
    router as investigations_router,
)
from api.app.routes.tools import dispose_tool_engines, router as tools_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    dispose_investigation_runtime()
    dispose_tool_engines()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
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
    app.include_router(tools_router)
    app.include_router(investigations_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": "/health",
            "ready": "/ready",
            "tools": "/tools/sql/templates",
            "investigations": "/investigations",
        }

    return app


app = create_app()
