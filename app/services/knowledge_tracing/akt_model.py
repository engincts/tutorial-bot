"""
AKT — Attentive Knowledge Tracing (Ghosh et al., 2020)

Gerçek AKT monotonic attention + Rasch embedding'leri ile
eğitim gerektirir. Bu dosya iki modda çalışır:

  1. checkpoint_path verilmemişse → DKT fallback (development/demo)
  2. checkpoint_path verilmişse   → PyTorch model yüklenir (production)

PyTorch modeli gelecekte buraya entegre edilecek.
Şu an için DKT'nin daha sofistike bir varyantını uyguluyoruz:
  - Monotonic decay: eski etkileşimler daha az ağırlık taşır
  - Per-KC ayrı state (DKT'nin global hidden state problemi yok)
  - Attempt count'a göre confidence scaling
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from app.services.knowledge_tracing.base import BaseKnowledgeTracer


@dataclass
class _KCState:
    p_mastery: float = 0.3
    attempts: int = 0
    # Son N etkileşimin ağırlıklı doğruluk geçmişi
    weighted_correct: float = 0.0
    weight_sum: float = 0.0


class AKTModel(BaseKnowledgeTracer):
    """
    AKT-inspired model:
    - Monotonic attention decay (recent > old)
    - Per-KC independent state
    - Confidence bound: az denemede tahmini ortaya çek
    """

    def __init__(
        self,
        checkpoint_path: str | None = None,
        decay_factor: float = 0.85,
        confidence_alpha: float = 5.0,
    ) -> None:
        self._decay = decay_factor
        self._alpha = confidence_alpha  # attempts → confidence hızı
        # {learner_id: {kc_id: _KCState}}
        self._state: dict[str, dict[str, _KCState]] = {}

        if checkpoint_path:
            self._load_checkpoint(checkpoint_path)

    def _load_checkpoint(self, path: str) -> None:
        """PyTorch checkpoint yükle — gelecekte implement edilecek."""
        import logging
        logging.getLogger(__name__).warning(
            "AKT checkpoint yükleme henüz implement edilmedi: %s. "
            "Heuristic model kullanılıyor.",
            path,
        )

    def _get_state(self, lid: str, kc_id: str) -> _KCState:
        if lid not in self._state:
            self._state[lid] = {}
        if kc_id not in self._state[lid]:
            self._state[lid][kc_id] = _KCState()
        return self._state[lid][kc_id]

    async def estimate(
        self,
        learner_id: uuid.UUID,
        kc_ids: list[str],
    ) -> dict[str, float]:
        lid = str(learner_id)
        result = {}
        for kc_id in kc_ids:
            state = self._get_state(lid, kc_id)
            result[kc_id] = self._compute_mastery(state)
        return result

    async def update(
        self,
        learner_id: uuid.UUID,
        kc_id: str,
        correct: bool,
    ) -> float:
        lid = str(learner_id)
        state = self._get_state(lid, kc_id)

        # Monotonic decay: önceki ağırlıkları azalt
        state.weighted_correct *= self._decay
        state.weight_sum *= self._decay

        # Yeni gözlemi ekle (ağırlık = 1.0, decay sonraki turda uygulanır)
        state.weighted_correct += 1.0 if correct else 0.0
        state.weight_sum += 1.0
        state.attempts += 1

        p_new = self._compute_mastery(state)
        state.p_mastery = p_new
        return p_new

    def _compute_mastery(self, state: _KCState) -> float:
        """
        Ağırlıklı doğruluk oranını hesapla,
        sonra attempt count'a göre ortaya çek (confidence scaling).
        """
        if state.weight_sum < 1e-9:
            return 0.3  # prior

        raw_accuracy = state.weighted_correct / state.weight_sum

        # Confidence: attempts arttıkça prior'dan uzaklaş
        # confidence → 0 when attempts=0, → 1 as attempts → ∞
        confidence = 1 - math.exp(-state.attempts / self._alpha)
        prior = 0.3

        p = prior + confidence * (raw_accuracy - prior)
        return max(0.0, min(1.0, p))
