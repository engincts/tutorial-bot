from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Tuple, Type

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from app.config_loader import JsonConfigSource


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    NOVITA = "novita"


class EmbedderProvider(StrEnum):
    BGE_M3 = "bge_m3"
    OPENAI = "openai"
    NOVITA = "novita"


class KTModel(StrEnum):
    AKT = "akt"
    DKT = "dkt"


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.OPENAI
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = Field(default="", repr=False)
    anthropic_model: str = "claude-sonnet-4-5"

    # ── Embedder ─────────────────────────────────────────────────────
    embedder_provider: EmbedderProvider = EmbedderProvider.BGE_M3
    embedder_model: str = "BAAI/bge-m3"
    openai_embedding_model: str = "text-embedding-3-large"
    novita_api_key: str = Field(default="", repr=False)
    novita_embedding_model: str = "baai/bge-m3"
    novita_llm_model: str = "meta-llama/llama-3.1-8b-instruct"
    embedding_dim: int = 1024

    # ── PostgreSQL ───────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "tutorbot"
    postgres_user: str = "tutorbot"
    postgres_password: str = Field(default="tutorbot_dev", repr=False)

    # ── Redis ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 3600

    # ── Knowledge Tracing ────────────────────────────────────────────
    kt_model: KTModel = KTModel.AKT
    kt_model_path: str = "./checkpoints/akt_assistments.pt"

    # ── Retrieval ────────────────────────────────────────────────────
    content_top_k: int = 5
    memory_top_k: int = 3
    rerank_enabled: bool = False

    # ── Pedagogy thresholds ──────────────────────────────────────────
    mastery_threshold_low: float = 0.4
    mastery_threshold_high: float = 0.7

    # ── App ──────────────────────────────────────────────────────────
    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: str = "INFO"

    # ── Supabase ─────────────────────────────────────────────────────
    supabase_url: str = Field(default="", repr=False)
    supabase_anon_key: str = Field(default="", repr=False)
    supabase_service_key: str = Field(default="", repr=False)
    supabase_jwt_secret: str = Field(default="", repr=False)

    # ── Computed ─────────────────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn_sync(self) -> str:
        """Alembic migration'ları için sync DSN."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Source priority: env vars > config.json > .env > defaults ────
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG002
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, JsonConfigSource(settings_cls), dotenv_settings)

    # ── Validation ───────────────────────────────────────────────────
    @model_validator(mode="after")
    def validate_api_keys(self) -> "Settings":
        if self.app_env == AppEnv.TEST:
            return self

        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY zorunlu — LLM_PROVIDER=openai seçildiğinde "
                "bu değer boş bırakılamaz."
            )
        if self.llm_provider == LLMProvider.ANTHROPIC and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY zorunlu — LLM_PROVIDER=anthropic seçildiğinde "
                "bu değer boş bırakılamaz."
            )
        if (
            self.embedder_provider == EmbedderProvider.OPENAI
            and not self.openai_api_key
        ):
            raise ValueError(
                "OPENAI_API_KEY zorunlu — EMBEDDER_PROVIDER=openai seçildiğinde "
                "bu değer boş bırakılamaz."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance. FastAPI Depends() ile kullanılır."""
    return Settings()
