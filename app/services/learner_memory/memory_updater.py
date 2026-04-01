"""
Post-response memory updater — LLM yanıt ürettikten SONRA async olarak çalışır.
Kullanıcıyı bekletmez: asyncio.create_task() ile tetiklenir.

Sorumluluklar:
  1. Etkileşimi embed et + pgvector'a yaz
  2. Misconception tespit edilmişse kaydet
  3. KT modelinden gelen yeni mastery değerlerini kc_mastery tablosuna upsert et
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.interaction import Interaction, Misconception
from app.services.learner_memory.interaction_logger import InteractionLogger
from app.services.learner_memory.misconception_store import MisconceptionStore
from app.services.learner_memory.profile_retriever import ProfileRetriever

logger = logging.getLogger(__name__)


class MemoryUpdater:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        interaction_logger: InteractionLogger,
        misconception_store: MisconceptionStore,
        profile_retriever: ProfileRetriever,
    ) -> None:
        self._session_factory = session_factory
        self._logger = interaction_logger
        self._misconception_store = misconception_store
        self._profile_retriever = profile_retriever

    async def update(
        self,
        interaction: Interaction,
        new_mastery: dict[str, float] | None = None,
        misconceptions: list[Misconception] | None = None,
    ) -> None:
        """
        Tüm post-response güncellemelerini tek transaction'da yapar.
        Hata olursa loglar, raise etmez — ana akışı kesmez.
        """
        try:
            async with self._session_factory() as session:
                # 1. Etkileşimi kaydet
                await self._logger.log(session, interaction)

                # 2. Yeni misconception'ları kaydet
                for misc in (misconceptions or []):
                    await self._misconception_store.add(
                        session,
                        learner_id=misc.learner_id,
                        kc_id=misc.kc_id,
                        description=misc.description,
                    )

                # 3. KT mastery güncellemeleri
                for kc_id, p_mastery in (new_mastery or {}).items():
                    await self._profile_retriever.upsert_kc_mastery(
                        session,
                        learner_id=interaction.learner_id,
                        kc_id=kc_id,
                        p_mastery=p_mastery,
                    )

                await session.commit()

        except Exception:
            logger.exception(
                "Memory update başarısız — learner_id=%s session_id=%s",
                interaction.learner_id,
                interaction.session_id,
            )

    def fire_and_forget(
        self,
        interaction: Interaction,
        new_mastery: dict[str, float] | None = None,
        misconceptions: list[Misconception] | None = None,
    ) -> asyncio.Task:
        """
        asyncio.create_task() ile arka planda başlatır.
        Response döndükten sonra çağrılır — kullanıcıyı bekletmez.
        """
        return asyncio.create_task(
            self.update(
                interaction=interaction,
                new_mastery=new_mastery,
                misconceptions=misconceptions,
            )
        )
