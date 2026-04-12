"""
Mastery Estimator — KT modelini ve KC mapper'ı bir araya getirir.
Orchestrator bu sınıfı kullanır, doğrudan modele erişmez.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.knowledge_component import KCMasterySnapshot, KnowledgeComponent
from app.services.knowledge_tracing.base import BaseKnowledgeTracer
from app.services.knowledge_tracing.kc_mapper import KCMapper
from app.services.learner_memory.profile_retriever import ProfileRetriever


class MasteryEstimator:
    def __init__(
        self,
        tracer: BaseKnowledgeTracer,
        kc_mapper: KCMapper,
        profile_retriever: ProfileRetriever,
    ) -> None:
        self._tracer = tracer
        self._mapper = kc_mapper
        self._profile_retriever = profile_retriever

    async def estimate_for_query(
        self,
        learner_id: uuid.UUID,
        query: str,
        known_kc_ids: list[str] | None = None,
        db_session: AsyncSession | None = None,
    ) -> tuple[list[str], KCMasterySnapshot]:
        """
        1. Sorgudan KC etiketleri çıkar
        2. DB'den mevcut mastery state'ini yükle (restart'tan kurtarır)
        3. O KC'ler için mastery tahminleri al
        4. KCMasterySnapshot döner
        """
        extracted = await self._mapper.extract(query)
        kc_ids = list(dict.fromkeys((known_kc_ids or []) + extracted))

        if not kc_ids:
            return [], KCMasterySnapshot()

        # DB'den mastery değerlerini yükleyip tracer'ı seed et
        if db_session is not None:
            db_snapshot = await self._profile_retriever.load_mastery_snapshot(
                db_session, learner_id, kc_ids
            )
            if db_snapshot.components:
                self._tracer.seed_state(
                    learner_id,
                    {kc_id: kc.p_mastery for kc_id, kc in db_snapshot.components.items()},
                )

        mastery_map = await self._tracer.estimate(learner_id=learner_id, kc_ids=kc_ids)

        snapshot = KCMasterySnapshot()
        for kc_id, p_mastery in mastery_map.items():
            snapshot.upsert(
                KnowledgeComponent(
                    kc_id=kc_id,
                    label=kc_id.replace("_", " ").title(),
                    p_mastery=p_mastery,
                )
            )

        return kc_ids, snapshot

    async def update_after_interaction(
        self,
        learner_id: uuid.UUID,
        kc_ids: list[str],
        correct: bool,
    ) -> dict[str, float]:
        """
        Etkileşim sonrası tüm ilgili KC'lerin mastery değerini günceller.
        Güncellenmiş {kc_id: p_mastery} dict döner.
        """
        updated = {}
        for kc_id in kc_ids:
            p_new = await self._tracer.update(
                learner_id=learner_id,
                kc_id=kc_id,
                correct=correct,
            )
            updated[kc_id] = p_new
        return updated
