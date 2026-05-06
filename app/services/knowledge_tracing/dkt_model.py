"""
DKT — Deep Knowledge Tracing (Piech et al., 2015)

Bu implementasyon gerçek bir LSTM eğitimi yerine
in-memory state ile Bayesian Knowledge Tracing formüllerini
kullanır. Gerçek bir DKT modeli fine-tune edildiğinde
bu sınıf PyTorch LSTM ağırlıklarını yüklemek üzere genişletilebilir.

Şu anki davranış:
  - Birinci gözlemde p_mastery = p_init (0.3)
  - Doğru cevap: mastery artar (learn rate)
  - Yanlış cevap: mastery azalır (forget rate)
  - Değerler [0, 1] arasında clamp edilir
"""
from __future__ import annotations

import uuid

from app.services.knowledge_tracing.base import BaseKnowledgeTracer


# Basit BKT parametreleri — gerçek DKT eğitiminde öğrenilir
_P_INIT = 0.3
_P_LEARN = 0.15
_P_FORGET = 0.05
_P_SLIP = 0.1
_P_GUESS = 0.2


class DKTModel(BaseKnowledgeTracer):
    """
    In-memory BKT-inspired fallback.
    Her learner_id için {kc_id: p_mastery} dict tutulur.
    Production'da bu state pgvector'dan yüklenir.
    """

    def __init__(self) -> None:
        # {learner_id: {kc_id: p_mastery}}
        self._state: dict[str, dict[str, float]] = {}

    def seed_state(self, learner_id: uuid.UUID, mastery_dict: dict[str, float]) -> None:
        lid = str(learner_id)
        if lid not in self._state:
            self._state[lid] = {}
        for kc_id, p_mastery in mastery_dict.items():
            if kc_id not in self._state[lid]:
                self._state[lid][kc_id] = p_mastery

    async def estimate(
        self,
        learner_id: uuid.UUID,
        kc_ids: list[str],
    ) -> dict[str, float]:
        lid = str(learner_id)
        learner_state = self._state.get(lid, {})
        return {kc_id: learner_state.get(kc_id, _P_INIT) for kc_id in kc_ids}

    async def update(
        self,
        learner_id: uuid.UUID,
        kc_id: str,
        correct: bool,
    ) -> float:
        lid = str(learner_id)
        if lid not in self._state:
            self._state[lid] = {}

        p = self._state[lid].get(kc_id, _P_INIT)

        # BKT posterior update
        if correct:
            # P(mastered | correct) ∝ P(correct | mastered) * P(mastered)
            p_correct_given_mastered = 1 - _P_SLIP
            p_correct_given_not = _P_GUESS
        else:
            p_correct_given_mastered = _P_SLIP
            p_correct_given_not = 1 - _P_GUESS

        numerator = p_correct_given_mastered * p
        denominator = numerator + p_correct_given_not * (1 - p)
        p_posterior = numerator / denominator if denominator > 0 else p

        # Learning/forgetting
        if correct:
            p_new = p_posterior + (1 - p_posterior) * _P_LEARN
        else:
            p_new = p_posterior * (1 - _P_FORGET)

        p_new = max(0.0, min(1.0, p_new))
        self._state[lid][kc_id] = p_new
        return p_new
