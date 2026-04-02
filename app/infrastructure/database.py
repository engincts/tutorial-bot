from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.settings import Settings, get_settings

# ── ORM Base ─────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ── Engine factory ────────────────────────────────────────────────────────────


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        f"postgresql+asyncpg:///{settings.postgres_db}",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=(settings.app_env.value == "development"),
        connect_args={
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "user": settings.postgres_user,
            "password": settings.postgres_password,
            "ssl": "disable",
        },
    )


# ── Session factory ───────────────────────────────────────────────────────────


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ── Module-level singletons (uygulama başlangıcında init edilir) ──────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings | None = None) -> None:
    global _engine, _session_factory
    settings = settings or get_settings()
    _engine = build_engine(settings)
    _session_factory = build_session_factory(_engine)


async def close_db() -> None:
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("DB başlatılmadı — init_db() çağrılmamış.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB başlatılmadı — init_db() çağrılmamış.")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends() ile kullanılan session dependency."""
    if _session_factory is None:
        raise RuntimeError("DB başlatılmadı — init_db() çağrılmamış.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
