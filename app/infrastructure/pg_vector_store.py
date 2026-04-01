"""
pgvector üzerinde iki ayrı koleksiyonu yönetir:
  - content_chunks   : müfredat / döküman parçaları
  - interaction_embeddings : öğrenci etkileşim geçmişi

Her iki tablo da aynı ORM base'i paylaşır.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base

# Embedding dim — env'den alınır, yoksa 1024 default
# Module-level settings çağrısı yapmıyoruz: test ortamında env olmayabilir
_EMBEDDING_DIM = int(__import__("os").environ.get("EMBEDDING_DIM", "1024"))

# ── ORM Models ────────────────────────────────────────────────────────────────


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(
        Vector(_EMBEDDING_DIM), nullable=False
    )
    kc_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    metadata_: Mapped[str] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class InteractionEmbedding(Base):
    __tablename__ = "interaction_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    interaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # question | misconception | success | struggle
    content_summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(
        Vector(_EMBEDDING_DIM), nullable=False
    )
    kc_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    correctness: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ── Vector Store ──────────────────────────────────────────────────────────────


class PgVectorStore:
    """
    İki koleksiyon üzerinde CRUD + similarity search sağlar.
    Her method bir AsyncSession alır — transaction yönetimi dışarıda.
    """

    # ── Content chunks ────────────────────────────────────────────────

    async def upsert_content_chunk(
        self,
        session: AsyncSession,
        document_id: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
        kc_tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContentChunk:
        import json

        chunk = ContentChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            embedding=embedding,
            kc_tags=kc_tags or [],
            metadata_=json.dumps(metadata or {}),
        )
        session.add(chunk)
        await session.flush()
        return chunk

    async def search_content(
        self,
        session: AsyncSession,
        query_embedding: list[float],
        top_k: int = 5,
        kc_filter: list[str] | None = None,
    ) -> list[ContentChunk]:
        """Cosine similarity ile en yakın content chunk'larını getirir."""
        stmt = (
            select(ContentChunk)
            .order_by(ContentChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        if kc_filter:
            stmt = stmt.where(ContentChunk.kc_tags.overlap(kc_filter))

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_document(self, session: AsyncSession, document_id: str) -> int:
        """Bir dökümana ait tüm chunk'ları siler. Kaç satır silindiğini döner."""
        result = await session.execute(
            text("DELETE FROM content_chunks WHERE document_id = :doc_id")
            .bindparams(doc_id=document_id)
        )
        return result.rowcount  # type: ignore[attr-defined]

    # ── Interaction embeddings ────────────────────────────────────────

    async def log_interaction(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        interaction_type: str,
        content_summary: str,
        embedding: list[float],
        kc_tags: list[str] | None = None,
        correctness: bool | None = None,
    ) -> InteractionEmbedding:
        record = InteractionEmbedding(
            learner_id=learner_id,
            session_id=session_id,
            interaction_type=interaction_type,
            content_summary=content_summary,
            embedding=embedding,
            kc_tags=kc_tags or [],
            correctness=correctness,
        )
        session.add(record)
        await session.flush()
        return record

    async def search_learner_memory(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 3,
        interaction_type_filter: str | None = None,
    ) -> list[InteractionEmbedding]:
        """Öğrencinin geçmiş etkileşimlerinden semantik olarak en yakınları getirir."""
        stmt = (
            select(InteractionEmbedding)
            .where(InteractionEmbedding.learner_id == learner_id)
            .order_by(InteractionEmbedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        if interaction_type_filter:
            stmt = stmt.where(
                InteractionEmbedding.interaction_type == interaction_type_filter
            )

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_interactions(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        limit: int = 10,
    ) -> list[InteractionEmbedding]:
        """En son N etkileşimi kronolojik sırayla getirir."""
        stmt = (
            select(InteractionEmbedding)
            .where(InteractionEmbedding.learner_id == learner_id)
            .order_by(InteractionEmbedding.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── Index management ──────────────────────────────────────────────

    async def ensure_hnsw_indexes(self, session: AsyncSession) -> None:
        """
        HNSW index'leri oluşturur (varsa atlar).
        Alembic migration'dan sonra bir kere çağrılır.
        """
        await session.execute(
            text("""
                CREATE INDEX IF NOT EXISTS content_chunks_embedding_hnsw
                ON content_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
        )
        await session.execute(
            text("""
                CREATE INDEX IF NOT EXISTS interaction_embeddings_hnsw
                ON interaction_embeddings
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
        )
        await session.commit()
