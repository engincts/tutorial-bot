"""
Mastery Estimator — KT modelini ve KC mapper'ı bir araya getirir.
Orchestrator bu sınıfı kullanır, doğrudan modele erişmez.
"""
from __future__ import annotations

import uuid

from app.domain.knowledge_component import KCMasterySnapshot, KnowledgeComponent
from app.services.knowledge_tracing.base import BaseKnowledgeTracer
from app.services.knowledge_tracing.kc_mapper import KCMapper


class MasteryEstimator:
    def __init__(
        self,
        tracer: BaseKnowledgeTracer,
        kc_mapper: KCMapper,
    ) -> None:
        self._tracer = tracer
        self._mapper = kc_mapper

    async def estimate_for_query(
        self,
        learner_id: uuid.UUID,
        query: str,
        known_kc_ids: list[str] | None = None,
    ) -> tuple[list[str], KCMasterySnapshot]:
        """
        1. Sorgudan KC etiketleri çıkar
        2. O KC'ler için mastery tahminleri al
        3. KCMasterySnapshot döner

        Dönüş: (kc_ids, snapshot)
        """
        # KC extraction + merge with known
        extracted = await self._mapper.extract(query)
        kc_ids = list(dict.fromkeys((known_kc_ids or []) + extracted))  # dedup, sıra koru

        if not kc_ids:
            return [], KCMasterySnapshot()

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
