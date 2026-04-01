"""FastAPI app factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, ingest, profile, session
from app.infrastructure.database import close_db, init_db
from app.infrastructure.redis_client import close_redis, init_redis
from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings)
    init_redis(settings)
    yield
    await close_db()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Tutor Bot API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env.value != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router)
    app.include_router(ingest.router)
    app.include_router(profile.router)
    app.include_router(session.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
