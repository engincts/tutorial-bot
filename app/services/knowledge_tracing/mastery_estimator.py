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
        course_names: list[str] | None = None,
    ) -> tuple[list[str], KCMasterySnapshot]:
        """
        1. Sorgudan KC etiketleri çıkar
        2. DB'den mevcut mastery state'ini yükle (restart'tan kurtarır)
        3. O KC'ler için mastery tahminleri al
        4. KCMasterySnapshot döner
        """
        extracted = await self._mapper.extract(query, course_names=course_names)
        kc_ids = list(dict.fromkeys((known_kc_ids or []) + extracted))

        if not kc_ids:
            return [], KCMasterySnapshot()

        # DB'den mastery değerlerini yükleyip tracer'ı seed et
        db_snapshot = KCMasterySnapshot()
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
            db_kc = db_snapshot.components.get(kc_id)
            
            # Ana ders adlarına (course_names) göre subject tespiti
            subject = "Genel"
            label_slug = kc_id
            
            if course_names:
                # En uzun eşleşmeyi bulmak için uzunluğa göre ters sırala
                sorted_courses = sorted(course_names, key=len, reverse=True)
                for course in sorted_courses:
                    if kc_id.startswith(course + "_"):
                        subject = course
                        label_slug = kc_id[len(course)+1:]
                        break
                    elif kc_id == course:
                        subject = course
                        label_slug = course
                        break
            
            if subject == "Genel":
                parts = kc_id.split("_")
                subject = parts[0]
                label_parts = parts[1:] if len(parts) > 1 else parts
                label = " ".join(label_parts).replace("_", " ").title()
            else:
                label = label_slug.replace("_", " ").title()

            snapshot.upsert(
                KnowledgeComponent(
                    kc_id=kc_id,
                    label=label,
                    p_mastery=p_mastery,
                    domain=db_kc.domain if (db_kc and db_kc.domain != "genel") else subject,
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
