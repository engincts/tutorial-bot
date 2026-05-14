"""
BKT — Bayesian Knowledge Tracing (Corbett & Anderson, 1994)

Eğitim teknolojisinin altın standardı. Hidden Markov Model tabanlı,
4 parametre ile öğrenci bilgi seviyesini takip eder.

Parametreler:
  P(L₀) — Başlangıç bilgi olasılığı (prior)
  P(T)  — Bir etkileşimde öğrenme olasılığı (transition)
  P(S)  — Biliyor ama yanlış yapma olasılığı (slip)
  P(G)  — Bilmiyor ama doğru tahmin etme olasılığı (guess)

Güncelleme:
  1. Bayes posterior: gözleme göre P(L) güncellenir
  2. Öğrenme geçişi: P(L_new) = P(L|obs) + (1 - P(L|obs)) * P(T)

LLM Hibrit Modu:
  Sohbet ortamında doğru/yanlış binary değil, LLM'den gelen
  güven skoru (0.0 - 1.0) kullanılarak "soft update" yapılır.
  Bu sayede sohbet tabanlı etkileşimlerde de BKT çalışır.
"""
from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field

from app.services.knowledge_tracing.base import BaseKnowledgeTracer

logger = logging.getLogger(__name__)


@dataclass
class _BKTState:
    """Bir öğrencinin bir KC'deki BKT durumu."""
    p_mastery: float = 0.1      # P(L) — mevcut bilgi olasılığı
    attempts: int = 0           # Toplam etkileşim sayısı
    correct_streak: int = 0     # Art arda doğru sayısı
    wrong_streak: int = 0       # Art arda yanlış sayısı


class BKTModel(BaseKnowledgeTracer):
    """
    Bayesian Knowledge Tracing — matematiksel olarak sağlam,
    kararlı ve yorumlanabilir bilgi izleme modeli.

    Özellikler:
    - Bayes posterior güncelleme (ani sıçrama yok)
    - Öğrenme geçişi (P(T)) ile kademeli artış
    - Slip/Guess parametreleri ile gürültüye dayanıklılık
    - Soft update: LLM güven skoru ile sohbet desteği
    - Forget faktörü: uzun süre etkileşim olmazsa hafif düşüş
    """

    def __init__(
        self,
        p_init: float = 0.1,       # Yeni bir konuda başlangıç seviyesi
        p_learn: float = 0.15,     # Her etkileşimde öğrenme olasılığı
        p_slip: float = 0.10,      # Bildiği halde yanlış yapma olasılığı
        p_guess: float = 0.20,     # Bilmediği halde doğru tahmin olasılığı
        p_forget: float = 0.02,    # Uzun süre görmezse unutma oranı
        min_mastery: float = 0.01, # Alt sınır — asla tam sıfır olmasın
        max_mastery: float = 0.99, # Üst sınır — asla tam 1.0 olmasın
    ) -> None:
        self._p_init = p_init
        self._p_learn = p_learn
        self._p_slip = p_slip
        self._p_guess = p_guess
        self._p_forget = p_forget
        self._min = min_mastery
        self._max = max_mastery

        # {learner_id_str: {kc_id: _BKTState}}
        self._state: dict[str, dict[str, _BKTState]] = {}

    # ── State Management ──────────────────────────────────────────

    def _get_state(self, lid: str, kc_id: str) -> _BKTState:
        if lid not in self._state:
            self._state[lid] = {}
        if kc_id not in self._state[lid]:
            self._state[lid][kc_id] = _BKTState(p_mastery=self._p_init)
        return self._state[lid][kc_id]

    def seed_state(self, learner_id: uuid.UUID, mastery_dict: dict[str, float]) -> None:
        """DB'den yüklenen mastery değerlerini in-memory state'e uygular."""
        lid = str(learner_id)
        for kc_id, p_mastery in mastery_dict.items():
            state = self._get_state(lid, kc_id)
            if state.attempts == 0:
                # Sadece hiç etkileşim olmamışsa DB değerini al
                state.p_mastery = max(self._min, min(self._max, p_mastery))

    # ── Core BKT Methods ──────────────────────────────────────────

    async def estimate(
        self,
        learner_id: uuid.UUID,
        kc_ids: list[str],
    ) -> dict[str, float]:
        """Verilen KC'ler için mevcut mastery tahminlerini döner."""
        lid = str(learner_id)
        return {kc_id: self._get_state(lid, kc_id).p_mastery for kc_id in kc_ids}

    async def update(
        self,
        learner_id: uuid.UUID,
        kc_id: str,
        correct: bool,
    ) -> float:
        """
        Binary gözlem (doğru/yanlış) ile BKT güncellemesi.

        Adım 1: Bayes Posterior — P(L|observation) hesapla
        Adım 2: Öğrenme Geçişi — P(L_new) = P(L|obs) + (1 - P(L|obs)) * P(T)
        """
        lid = str(learner_id)
        state = self._get_state(lid, kc_id)

        p_l = state.p_mastery

        # ── Adım 1: Bayes Posterior ──
        if correct:
            # P(L | correct) = P(correct|L) * P(L) / P(correct)
            # P(correct|L) = 1 - P(S)
            # P(correct|¬L) = P(G)
            p_obs_given_l = 1.0 - self._p_slip
            p_obs_given_not_l = self._p_guess
            state.correct_streak += 1
            state.wrong_streak = 0
        else:
            # P(L | wrong) = P(wrong|L) * P(L) / P(wrong)
            # P(wrong|L) = P(S)
            # P(wrong|¬L) = 1 - P(G)
            p_obs_given_l = self._p_slip
            p_obs_given_not_l = 1.0 - self._p_guess
            state.wrong_streak += 1
            state.correct_streak = 0

        numerator = p_obs_given_l * p_l
        denominator = numerator + p_obs_given_not_l * (1.0 - p_l)

        if denominator > 1e-10:
            p_posterior = numerator / denominator
        else:
            p_posterior = p_l

        # ── Adım 2: Öğrenme Geçişi ──
        # P(L_new) = P(L|obs) + (1 - P(L|obs)) * P(T)
        p_new = p_posterior + (1.0 - p_posterior) * self._p_learn

        # Yanlış cevaplarda hafif unutma uygula
        if not correct:
            p_new = p_new * (1.0 - self._p_forget)

        # Clamp
        p_new = max(self._min, min(self._max, p_new))
        state.p_mastery = p_new
        state.attempts += 1

        return p_new

    async def soft_update(
        self,
        learner_id: uuid.UUID,
        kc_id: str,
        confidence: float,
    ) -> float:
        """
        LLM güven skoru ile "yumuşak" güncelleme.
        Sohbet ortamında kullanılır — binary doğru/yanlış yerine
        0.0-1.0 arası bir güven skoru alır.

        Güven skoru:
          0.0 = Kesinlikle bilmiyor
          0.5 = Kısmen biliyor
          1.0 = Kesinlikle biliyor

        Strateji: Güven skorunu ağırlıklı olarak doğru ve yanlış
        gözlem olasılıklarının karışımı olarak kullanır.
        """
        lid = str(learner_id)
        state = self._get_state(lid, kc_id)

        p_l = state.p_mastery

        # Güven skorunu ağırlıklı Bayes güncellemesine çevir
        # confidence=1.0 → tamamen "doğru" gözlem
        # confidence=0.0 → tamamen "yanlış" gözlem
        # confidence=0.5 → bilgi değişmez (nötr)

        # Ağırlıklı olasılıklar
        p_obs_given_l = confidence * (1.0 - self._p_slip) + (1.0 - confidence) * self._p_slip
        p_obs_given_not_l = confidence * self._p_guess + (1.0 - confidence) * (1.0 - self._p_guess)

        numerator = p_obs_given_l * p_l
        denominator = numerator + p_obs_given_not_l * (1.0 - p_l)

        if denominator > 1e-10:
            p_posterior = numerator / denominator
        else:
            p_posterior = p_l

        # Öğrenme geçişi — güven skoruna orantılı
        effective_learn = self._p_learn * confidence
        p_new = p_posterior + (1.0 - p_posterior) * effective_learn

        # Düşük güven → hafif unutma
        if confidence < 0.3:
            p_new = p_new * (1.0 - self._p_forget)

        p_new = max(self._min, min(self._max, p_new))
        state.p_mastery = p_new
        state.attempts += 1

        return p_new
