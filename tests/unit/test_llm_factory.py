"""LLM factory — doğru client'ı döndüğünü test eder."""
import pytest
from unittest.mock import patch

from app.settings import AppEnv, EmbedderProvider, LLMProvider, Settings
from app.infrastructure.llm import build_llm_client


def make_settings(**overrides) -> Settings:
    base = dict(
        app_env=AppEnv.TEST,
        openai_api_key="sk-test",
        anthropic_api_key="sk-ant-test",
        embedder_provider=EmbedderProvider.BGE_M3,
    )
    base.update(overrides)
    return Settings(**base)


def test_openai_provider_returns_openai_client():
    from app.infrastructure.llm.openai_client import OpenAIClient
    s = make_settings(llm_provider=LLMProvider.OPENAI)
    client = build_llm_client(s)
    assert isinstance(client, OpenAIClient)


def test_anthropic_provider_returns_anthropic_client():
    from app.infrastructure.llm.anthropic_client import AnthropicClient
    s = make_settings(llm_provider=LLMProvider.ANTHROPIC)
    client = build_llm_client(s)
    assert isinstance(client, AnthropicClient)


def test_unknown_provider_raises():
    s = make_settings()
    s.llm_provider = "unknown_provider"  # type: ignore
    with pytest.raises(ValueError, match="Bilinmeyen LLM_PROVIDER"):
        build_llm_client(s)
