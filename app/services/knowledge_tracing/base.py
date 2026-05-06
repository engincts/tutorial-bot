"""
Abstract KnowledgeTracer interface.
Tüm KT modelleri bu contract'ı implement eder.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class BaseKnowledgeTracer(ABC):
    """
    Bir öğrencinin KC mastery olasılıklarını tahmin eder.

    estimate() → sonraki etkileşimden ÖNCE çağrılır (mevcut durum)
    update()   → etkileşim gerçekleştikten SONRA çağrılır (yeni gözlem)
    seed_state() → DB'den yüklenen değerlerle in-memory state'i senkronize eder
    """

    def seed_state(self, learner_id: uuid.UUID, mastery_dict: dict[str, float]) -> None:
        """
        DB'den yüklenen mastery değerlerini in-memory state'e uygular.
        Restart sonrası öğrenci state'ini geri yükler.
        Sadece hiç görülmemiş KC'ler için override eder.
        """

    @abstractmethod
    async def estimate(
        self,
        learner_id: uuid.UUID,
        kc_ids: list[str],
    ) -> dict[str, float]:
        """
        Verilen KC listesi için mastery olasılıklarını döner.
        Dönüş: {kc_id: p_mastery} — değerler [0, 1] aralığında
        """
        ...

    @abstractmethod
    async def update(
        self,
        learner_id: uuid.UUID,
        kc_id: str,
        correct: bool,
    ) -> float:
        """
        Yeni bir gözlem (doğru/yanlış) ile mastery tahminini günceller.
        Güncellenmiş p_mastery döner.
        """
        ...
