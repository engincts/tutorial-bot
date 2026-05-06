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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing import TYPE_CHECKING

from app.domain.interaction import Interaction, Misconception
from app.services.learner_memory.interaction_logger import InteractionLogger
from app.services.learner_memory.profile_retriever import ProfileRetriever
from app.services.knowledge_tracing.llm_mastery_evaluator import LLMMasteryEvaluator
from app.services.learner_memory.reflection_generator import ReflectionGenerator

if TYPE_CHECKING:
    from app.services.orchestration.hallucination_monitor import HallucinationMonitor

logger = logging.getLogger(__name__)


class MemoryUpdater:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        interaction_logger: InteractionLogger,
        misconception_store: MisconceptionStore,
        profile_retriever: ProfileRetriever,
        mastery_evaluator: LLMMasteryEvaluator,
        reflection_generator: ReflectionGenerator | None = None,
        hallucination_monitor: 'HallucinationMonitor' | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._logger = interaction_logger
        self._misconception_store = misconception_store
        self._profile_retriever = profile_retriever
        self._mastery_evaluator = mastery_evaluator
        self._reflection_generator = reflection_generator
        self._hallucination_monitor = hallucination_monitor

    async def update(
        self,
        interaction: Interaction,
        new_mastery: dict[str, float] | None = None,
        misconceptions: list[Misconception] | None = None,
        subject: str | None = None,
        user_message: str | None = None,
        assistant_response: str | None = None,
        context_used: str | None = None,
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

                # 3. LLM Mastery Evaluation (eğer new_mastery verilmemişse)
                eval_mastery = new_mastery or {}
                if not eval_mastery and user_message and assistant_response and interaction.kc_tags:
                    snapshot = await self._profile_retriever.load_mastery_snapshot(session, interaction.learner_id, interaction.kc_tags)
                    current_mastery = {kc.kc_id: kc.p_mastery for kc in snapshot.components.values()}
                    eval_mastery = await self._mastery_evaluator.evaluate(
                        user_message=user_message,
                        assistant_response=assistant_response,
                        kc_ids=interaction.kc_tags,
                        current_mastery=current_mastery
                    )

                # 4. KT mastery güncellemeleri
                for kc_id, p_mastery in eval_mastery.items():
                    # KC ID'nin ilk parçası = ders; fallback olarak genel subject kullan
                    per_kc_subject = kc_id.split("_")[0] or subject
                    await self._profile_retriever.upsert_kc_mastery(
                        session,
                        learner_id=interaction.learner_id,
                        kc_id=kc_id,
                        p_mastery=p_mastery,
                        subject=per_kc_subject,
                    )

                # 5. Reflection tetiklemesi
                if self._reflection_generator:
                    reflection = await self._reflection_generator.generate_reflection(session, interaction.learner_id)
                    if reflection:
                        import json
                        # Log it as a new interaction
                        from app.domain.interaction import InteractionType
                        ref_interaction = Interaction(
                            learner_id=interaction.learner_id,
                            session_id=interaction.session_id,
                            interaction_type=InteractionType("reflection"),
                            content_summary=json.dumps(reflection),
                            kc_tags=[]
                        )
                        await self._logger.log(session, ref_interaction)
                        
                        # update profile preferences
                        profile = await self._profile_retriever.get_profile(session, interaction.learner_id)
                        if profile:
                            prefs = json.loads(profile.preferences) if profile.preferences else {}
                            prefs["last_reflection"] = reflection
                            from sqlalchemy import update, text
                            from sqlalchemy.dialects.postgresql import UUID
                            await session.execute(
                                text("UPDATE student_profiles SET preferences = :prefs WHERE id = :lid")
                                .bindparams(prefs=json.dumps(prefs), lid=profile.learner_id)
                            )
                            
                # 6. Hallucination check
                if self._hallucination_monitor and assistant_response and context_used:
                    await self._hallucination_monitor.evaluate(
                        session=session,
                        learner_id=interaction.learner_id,
                        session_id=interaction.session_id,
                        assistant_response=assistant_response,
                        context_used=context_used,
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
        subject: str | None = None,
        user_message: str | None = None,
        assistant_response: str | None = None,
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
                subject=subject,
                user_message=user_message,
                assistant_response=assistant_response,
            )
        )
