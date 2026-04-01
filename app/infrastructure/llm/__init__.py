from functools import lru_cache

from app.infrastructure.llm.base import BaseLLMClient, LLMResponse, Message
from app.settings import LLMProvider, Settings, get_settings


def build_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    settings = settings or get_settings()
    if settings.llm_provider == LLMProvider.OPENAI:
        from app.infrastructure.llm.openai_client import OpenAIClient
        return OpenAIClient(settings)
    if settings.llm_provider == LLMProvider.ANTHROPIC:
        from app.infrastructure.llm.anthropic_client import AnthropicClient
        return AnthropicClient(settings)
    if settings.llm_provider == LLMProvider.NOVITA:
        from app.infrastructure.llm.novita_client import NovitaClient
        return NovitaClient(settings)
    raise ValueError(f"Bilinmeyen LLM_PROVIDER: {settings.llm_provider}")


@lru_cache(maxsize=1)
def get_llm_client() -> BaseLLMClient:
    """Singleton LLM client instance."""
    return build_llm_client()


__all__ = ["BaseLLMClient", "LLMResponse", "Message", "build_llm_client", "get_llm_client"]
