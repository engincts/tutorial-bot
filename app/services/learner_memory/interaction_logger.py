"""
Etkileşim kayıt servisi — her konuşma turunu embed ederek pgvector'a yazar.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interaction import Interaction, InteractionType
from app.infrastructure.embedder_factory import BaseEmbedder
from app.infrastructure.pg_vector_store import PgVectorStore


class InteractionLogger:
    def __init__(self, embedder: BaseEmbedder, vector_store: PgVectorStore) -> None:
        self._embedder = embedder
        self._store = vector_store

    async def log(
        self,
        session: AsyncSession,
        interaction: Interaction,
    ) -> None:
        """
        Bir etkileşimi embed ederek interaction_embeddings tablosuna yazar.
        """
        embed_text = interaction.to_embed_text()
        embedding = await self._embedder.embed(embed_text)

        await self._store.log_interaction(
            session=session,
            learner_id=interaction.learner_id,
            session_id=interaction.session_id,
            interaction_type=interaction.interaction_type.value,
            content_summary=interaction.content_summary,
            embedding=embedding,
            kc_tags=interaction.kc_tags,
            correctness=interaction.correctness,
        )

    async def log_many(
        self,
        session: AsyncSession,
        interactions: list[Interaction],
    ) -> None:
        """Batch embed + log — birden fazla etkileşim için."""
        if not interactions:
            return

        texts = [i.to_embed_text() for i in interactions]
        embeddings = await self._embedder.embed_batch(texts)

        for interaction, embedding in zip(interactions, embeddings):
            await self._store.log_interaction(
                session=session,
                learner_id=interaction.learner_id,
                session_id=interaction.session_id,
                interaction_type=interaction.interaction_type.value,
                content_summary=interaction.content_summary,
                embedding=embedding,
                kc_tags=interaction.kc_tags,
                correctness=interaction.correctness,
            )
