"""
Döküman alım hattı — PDF / Markdown / düz metin → chunk → embed → pgvector.

Akış:
  raw_text → Chunker → embed_batch → PgVectorStore.upsert_content_chunk
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.embedder_factory import BaseEmbedder
from app.infrastructure.pg_vector_store import PgVectorStore
from app.services.content_rag.chunker import Chunker, TextChunk

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    document_id: str
    chunks_written: int
    chars_total: int


class IngestionPipeline:
    def __init__(
        self,
        chunker: Chunker,
        embedder: BaseEmbedder,
        vector_store: PgVectorStore,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._store = vector_store

    async def ingest_text(
        self,
        session: AsyncSession,
        document_id: str,
        text: str,
        kc_tags: list[str] | None = None,
        metadata: dict | None = None,
        replace_existing: bool = True,
    ) -> IngestionResult:
        """
        Ham metni chunk'lara böler, embed eder ve pgvector'a yazar.
        replace_existing=True ise önce eski chunk'ları siler.
        """
        if replace_existing:
            deleted = await self._store.delete_document(session, document_id)
            if deleted:
                logger.info("Döküman güncelleniyor: %s (%d chunk silindi)", document_id, deleted)

        chunks: list[TextChunk] = self._chunker.chunk(text)
        if not chunks:
            logger.warning("Döküman boş veya chunk üretilemedi: %s", document_id)
            return IngestionResult(document_id=document_id, chunks_written=0, chars_total=0)

        # Batch embed — tüm chunk'ları tek API çağrısıyla embed et
        texts = [c.text for c in chunks]
        embeddings = await self._embedder.embed_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**(metadata or {}), "heading": chunk.heading}
            await self._store.upsert_content_chunk(
                session=session,
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.text,
                embedding=embedding,
                kc_tags=kc_tags or [],
                metadata=chunk_meta,
            )

        chars_total = sum(len(c.text) for c in chunks)
        logger.info(
            "İşlendi: %s → %d chunk, %d karakter",
            document_id,
            len(chunks),
            chars_total,
        )
        return IngestionResult(
            document_id=document_id,
            chunks_written=len(chunks),
            chars_total=chars_total,
        )

    async def ingest_pdf(
        self,
        session: AsyncSession,
        document_id: str,
        pdf_bytes: bytes,
        kc_tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> IngestionResult:
        """PDF'yi metne çevirir, ardından ingest_text'e iletir."""
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(pages)
        except Exception as exc:
            logger.error("PDF parse hatası (%s): %s", document_id, exc)
            raise

        return await self.ingest_text(
            session=session,
            document_id=document_id,
            text=text,
            kc_tags=kc_tags,
            metadata={**(metadata or {}), "source_type": "pdf"},
        )
