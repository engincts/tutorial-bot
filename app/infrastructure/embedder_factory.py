"""
Embedding factory — provider seçimine göre doğru client'ı döner.
Tüm embedder'lar tek interface: embed(text) -> list[float]
                                embed_batch(texts) -> list[list[float]]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

import numpy as np

from app.settings import EmbedderProvider, Settings, get_settings


# ── Base interface ────────────────────────────────────────────────────────────


class BaseEmbedder(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dim(self) -> int: ...


# ── BGE-M3 (local, self-hosted) ───────────────────────────────────────────────


class BGEM3Embedder(BaseEmbedder):
    """
    sentence-transformers üzerinden BGE-M3.
    İlk çağrıda model yüklenir (~2GB VRAM veya CPU).
    """

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model_name = model_name
        self._model = None  # lazy load

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)

    async def embed(self, text: str) -> list[float]:
        self._load()
        # sentence-transformers sync — ama embedding işlemi CPU/GPU bound,
        # production'da run_in_executor kullanılabilir
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load()
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return vecs.tolist()

    @property
    def dim(self) -> int:
        return 1024


# ── OpenAI Embedder ───────────────────────────────────────────────────────────


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            input=text,
            model=self._model,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            input=texts,
            model=self._model,
        )
        # OpenAI garantisi: sıra korunur
        return [item.embedding for item in response.data]

    @property
    def dim(self) -> int:
        return 3072  # text-embedding-3-large varsayılan


# ── Factory ───────────────────────────────────────────────────────────────────


def build_embedder(settings: Settings | None = None) -> BaseEmbedder:
    settings = settings or get_settings()
    if settings.embedder_provider == EmbedderProvider.BGE_M3:
        return BGEM3Embedder(model_name=settings.embedder_model)
    if settings.embedder_provider == EmbedderProvider.OPENAI:
        return OpenAIEmbedder(settings=settings)
    raise ValueError(f"Bilinmeyen EMBEDDER_PROVIDER: {settings.embedder_provider}")


@lru_cache(maxsize=1)
def get_embedder() -> BaseEmbedder:
    """Singleton embedder instance."""
    return build_embedder()
