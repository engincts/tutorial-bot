"""
Content retriever — kullanıcı sorgusuna semantik olarak en yakın
curriculum chunk'larını getirir.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.embedder_factory import BaseEmbedder
from app.infrastructure.pg_vector_store import ContentChunk, PgVectorStore

if TYPE_CHECKING:
    from app.services.content_rag.reranker import Reranker


@dataclass
class RetrievedChunk:
    document_id: str
    chunk_index: int
    content: str
    heading: str
    kc_tags: list[str]


class ContentRetriever:
    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: PgVectorStore,
        top_k: int = 5,
        reranker: Reranker | None = None,
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._top_k = top_k
        self._reranker = reranker

    async def embed(self, text: str) -> list[float]:
        return await self._embedder.embed(text)

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        embedding: list[float] | None = None,
        kc_filter: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Sorguyu embed eder ve pgvector'dan en yakın chunk'ları getirir.
        embedding verilirse yeniden embed etmez — orchestrator'dan geçirilen embedding kullanılır.
        kc_filter verilirse sadece o KC etiketlerini içeren chunk'ları döner.
        """
        query_embedding = embedding if embedding is not None else await self._embedder.embed(query)
        k = top_k or self._top_k

        raw_chunks: list[ContentChunk] = await self._store.search_content(
            session=session,
            query_embedding=query_embedding,
            top_k=k,
            kc_filter=kc_filter,
        )

        chunks = [self._to_retrieved(c) for c in raw_chunks]

        if self._reranker and chunks:
            chunks = await self._reranker.rerank(query=query, chunks=chunks, top_k=k)

        return chunks

    def to_prompt_context(self, chunks: list[RetrievedChunk]) -> str:
        """Prompt'a eklenecek kaynak içeriği formatlar."""
        if not chunks:
            return ""
        parts = ["İlgili kaynak içeriği:"]
        for i, chunk in enumerate(chunks, 1):
            heading_prefix = f"[{chunk.heading}] " if chunk.heading else ""
            parts.append(f"\n--- Kaynak {i} ({chunk.document_id}) ---")
            parts.append(f"{heading_prefix}{chunk.content}")
        return "\n".join(parts)

    @staticmethod
    def _to_retrieved(chunk: ContentChunk) -> RetrievedChunk:
        try:
            meta = json.loads(chunk.metadata_ or "{}")
        except Exception:
            meta = {}
        return RetrievedChunk(
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            heading=meta.get("heading", ""),
            kc_tags=chunk.kc_tags or [],
        )
