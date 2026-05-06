"""FastAPI app factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.routes import auth, chat, conversations, ingest, profile, session, quiz
from app.infrastructure.database import close_db, init_db
from app.infrastructure.redis_client import close_redis, init_redis
from app.logging_config import configure_logging
from app.settings import get_settings

logger = logging.getLogger(__name__)

_ready = False  # Readiness flag


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready
    settings = get_settings()

    # JSON logging for production
    if settings.app_env.value == "production":
        from app.logging_json import configure_json_logging
        configure_json_logging(log_level=settings.log_level)
    else:
        configure_logging(log_level=settings.log_level)

    logger.info("Starting Tutor Bot | env=%s | llm=%s", settings.app_env, settings.llm_provider)
    init_db(settings)
    init_redis(settings)
    logger.info("Database and Redis initialized")
    _ready = True
    yield
    _ready = False
    logger.info("Shutting down Tutor Bot")
    await close_db()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Tutor Bot API",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env.value != "production" else None,
        swagger_ui_parameters={"persistAuthorization": True},
    )

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    # ── Middleware ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Metrics middleware
    from app.api.middleware.metrics import setup_metrics
    setup_metrics(app)

    # Tracing middleware
    from app.api.middleware.tracing import setup_tracing
    setup_tracing(app)

    # ── Routes ──
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(ingest.router)
    app.include_router(profile.router)
    app.include_router(session.router)
    app.include_router(quiz.router)

    # Admin routes
    from app.api.routes import admin, export, upload
    app.include_router(admin.router)
    app.include_router(export.router)
    app.include_router(upload.router)

    # ── Health probes ──
    @app.get("/health")
    async def health():
        from sqlalchemy import text as sa_text
        from app.infrastructure.database import get_engine
        from app.infrastructure.redis_client import get_redis
        from app.api.middleware.metrics import set_dlq_size

        checks: dict = {}

        try:
            await get_redis().ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

        try:
            async with get_engine().connect() as conn:
                await conn.execute(sa_text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"

        try:
            redis_client = get_redis()
            dlq_size = await redis_client.llen("worker:memory_dlq")
            checks["dlq_size"] = dlq_size
            set_dlq_size(dlq_size)
            if dlq_size > 10:
                logger.error("CRITICAL: DLQ size exceeded threshold: %d", dlq_size)
        except Exception:
            checks["dlq_size"] = "error"

        checks["status"] = "ok" if checks.get("redis") == "ok" and checks.get("database") == "ok" else "degraded"
        return checks

    @app.get("/healthz", include_in_schema=False)
    async def liveness():
        """Kubernetes liveness probe — uygulama çalışıyor mu?"""
        return {"status": "alive"}

    @app.get("/readyz", include_in_schema=False)
    async def readiness():
        """Kubernetes readiness probe — uygulama trafik almaya hazır mı?"""
        if not _ready:
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    return app


app = create_app()

