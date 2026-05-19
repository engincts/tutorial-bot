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
                _EXAM_PREFIXES = frozenset(["tyt", "ayt", "yks", "lgs", "kpss", "ales"])
                existing = locals().get("current_mastery", {})
                for kc_id in interaction.kc_tags:
                    llm_score = eval_mastery.get(kc_id)
                    old_p = existing.get(kc_id, 0.3)

                    if llm_score is not None:
                        learning_rate = 0.2
                        p_mastery = old_p + learning_rate * (llm_score - old_p)
                        p_mastery = max(0.01, min(0.99, p_mastery))
                    elif kc_id in existing:
                        p_mastery = old_p
                    else:
                        p_mastery = 0.3

                    # Her KC'ye kendi kc_id'sinden türetilen doğru subject yaz
                    parts = kc_id.split("_")
                    if parts and parts[0].lower() in _EXAM_PREFIXES:
                        per_kc_subject = parts[1] if len(parts) > 1 else parts[0]
                    else:
                        per_kc_subject = parts[0] if parts else kc_id

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
                        profile = await self._profile_retriever.get_or_create(session, interaction.learner_id)
                        if profile:
                            prefs = profile.preferences or {}
                            prefs["last_reflection"] = reflection
                            from sqlalchemy import update, text
                            from sqlalchemy.dialects.postgresql import UUID
                            await session.execute(
                                text("UPDATE student_profiles SET preferences = :prefs WHERE id = :lid")
                                .bindparams(prefs=json.dumps(prefs), lid=profile.id)
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
