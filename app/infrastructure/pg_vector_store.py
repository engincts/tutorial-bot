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

from app.settings import get_settings

_EMBEDDING_DIM = get_settings().embedding_dim

# ── ORM Models ────────────────────────────────────────────────────────────────


class ContentChunk(Base):
    __tablename__ = "curriculum_chunks"

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
    __tablename__ = "chat_history"

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
        query: str,
        query_embedding: list[float],
        top_k: int = 5,
        kc_filter: list[str] | None = None,
    ) -> list[ContentChunk]:
        """Hybrid search (Dense + Sparse pg_trgm) with RRF (Reciprocal Rank Fusion)."""
        # CTEs for dense and sparse rankings
        filter_clause = ""
        if kc_filter:
            # Postgres ARRAY overlap operator
            formatted_filter = "ARRAY[" + ",".join([f"'{k}'" for k in kc_filter]) + "]::varchar[]"
            filter_clause = f"WHERE kc_tags && {formatted_filter}"

        sql = f"""
        WITH dense_search AS (
            SELECT id, 
                   row_number() OVER (ORDER BY embedding <=> :embedding::vector) as rank
            FROM curriculum_chunks
            {filter_clause}
            LIMIT 50
        ),
        sparse_search AS (
            SELECT id,
                   row_number() OVER (ORDER BY similarity(content, :query) DESC) as rank
            FROM curriculum_chunks
            {filter_clause}
            LIMIT 50
        ),
        rrf AS (
            SELECT
                COALESCE(d.id, s.id) as id,
                COALESCE(1.0 / (60 + d.rank), 0.0) + COALESCE(1.0 / (60 + s.rank), 0.0) as rrf_score
            FROM dense_search d
            FULL OUTER JOIN sparse_search s ON d.id = s.id
            ORDER BY rrf_score DESC
            LIMIT :top_k
        )
        SELECT c.*
        FROM curriculum_chunks c
        JOIN rrf r ON c.id = r.id
        ORDER BY r.rrf_score DESC;
        """
        
        result = await session.execute(
            text(sql),
            {"embedding": query_embedding, "query": query, "top_k": top_k}
        )
        
        # We need to map raw rows back to ContentChunk models
        # But text() returns Row objects, not ORM models directly
        # Let's use session.scalars with FromStatement
        
        stmt = select(ContentChunk).from_statement(text(sql))
        result_orm = await session.scalars(
            stmt,
            {"embedding": query_embedding, "query": query, "top_k": top_k}
        )
        return list(result_orm.all())

    async def delete_document(self, session: AsyncSession, document_id: str) -> int:
        """Bir dökümana ait tüm chunk'ları siler. Kaç satır silindiğini döner."""
        result = await session.execute(
            text("DELETE FROM curriculum_chunks WHERE document_id = :doc_id")
            .bindparams(doc_id=document_id)
        )
        return result.rowcount  # type: ignore[attr-defined]

    async def get_all_document_ids(self, session: AsyncSession) -> list[str]:
        """Tüm benzersiz document_id (ders adı) değerlerini getirir."""
        result = await session.execute(select(ContentChunk.document_id).distinct())
        return list(result.scalars().all())

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
                CREATE INDEX IF NOT EXISTS curriculum_chunks_embedding_hnsw
                ON curriculum_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
        )
        await session.execute(
            text("""
                CREATE INDEX IF NOT EXISTS chat_history_embedding_hnsw
                ON chat_history
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
        )
        await session.commit()
