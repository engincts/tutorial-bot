"""Settings validation ve factory testleri."""
import os
import pytest
from app.settings import (
    AppEnv,
    EmbedderProvider,
    KTModel,
    LLMProvider,
    Settings,
)


def make_settings(**overrides) -> Settings:
    base = dict(
        app_env=AppEnv.TEST,
        llm_provider=LLMProvider.OPENAI,
        openai_api_key="sk-test",
        embedder_provider=EmbedderProvider.BGE_M3,
    )
    base.update(overrides)
    return Settings(**base)


def test_postgres_dsn_format():
    s = make_settings(
        postgres_user="user",
        postgres_password="pass",
        postgres_host="db",
        postgres_port=5432,
        postgres_db="mydb",
    )
    assert s.postgres_dsn == "postgresql+asyncpg://user:pass@db:5432/mydb"


def test_openai_key_required_in_production():
    with pytest.raises(ValueError, match="OPENAI_API_KEY zorunlu"):
        Settings(
            app_env=AppEnv.PRODUCTION,
            llm_provider=LLMProvider.OPENAI,
            openai_api_key="",
        )


def test_anthropic_key_required_in_production():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY zorunlu"):
        Settings(
            app_env=AppEnv.PRODUCTION,
            llm_provider=LLMProvider.ANTHROPIC,
            anthropic_api_key="",
        )


def test_test_env_skips_key_validation():
    # TEST ortamında boş key kabul edilmeli
    s = make_settings(openai_api_key="")
    assert s.app_env == AppEnv.TEST


def test_kt_model_default():
    s = make_settings()
    assert s.kt_model == KTModel.AKT


def test_mastery_thresholds():
    s = make_settings(mastery_threshold_low=0.35, mastery_threshold_high=0.75)
    assert s.mastery_threshold_low == 0.35
    assert s.mastery_threshold_high == 0.75
