"""
Knowledge Component (KC) — öğrenilmesi gereken bir kavram birimi.
Mastery tahmini bu granülaritede yapılır.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MasteryLevel(StrEnum):
    UNKNOWN = "unknown"        # hiç karşılaşılmamış
    INTRODUCED = "introduced"  # tanıtıldı, henüz pekişmedi
    PRACTICING = "practicing"  # pratik yapılıyor (0.4–0.7)
    MASTERED = "mastered"      # öğrenildi (> 0.7)


@dataclass
class KnowledgeComponent:
    """Bir knowledge component ve o andaki mastery durumu."""

    kc_id: str                        # örn: "quadratic_equations", "photosynthesis"
    label: str                        # kullanıcıya gösterilecek ad
    p_mastery: float = 0.3            # [0, 1] — AKT/DKT çıktısı
    attempts: int = 0
    domain: str = "general"           # hangi alana ait

    @property
    def mastery_level(self) -> MasteryLevel:
        if self.attempts == 0:
            return MasteryLevel.UNKNOWN
        if self.p_mastery < 0.4:
            return MasteryLevel.INTRODUCED
        if self.p_mastery < 0.7:
            return MasteryLevel.PRACTICING
        return MasteryLevel.MASTERED

    def update(self, new_p_mastery: float) -> None:
        """KT modelinden gelen yeni tahminle güncelle."""
        self.p_mastery = max(0.0, min(1.0, new_p_mastery))
        self.attempts += 1


@dataclass
class KCMasterySnapshot:
    """Bir oturum anında tüm ilgili KC'lerin anlık durumu."""
    components: dict[str, KnowledgeComponent] = field(default_factory=dict)

    def get(self, kc_id: str) -> KnowledgeComponent | None:
        return self.components.get(kc_id)

    def upsert(self, kc: KnowledgeComponent) -> None:
        self.components[kc.kc_id] = kc

    def weakest(self, n: int = 3) -> list[KnowledgeComponent]:
        """En az bilinen N konuyu döner — pedagoji planlayıcı için."""
        known = [kc for kc in self.components.values() if kc.attempts > 0]
        return sorted(known, key=lambda k: k.p_mastery)[:n]

    def to_prompt_context(self) -> str:
        """Prompt'a eklenecek mastery özeti."""
        if not self.components:
            return "Henüz bilinen konu yok."
        lines = []
        for kc in sorted(self.components.values(), key=lambda k: k.p_mastery):
            bar = "█" * int(kc.p_mastery * 10) + "░" * (10 - int(kc.p_mastery * 10))
            lines.append(
                f"- {kc.label}: {bar} {kc.p_mastery:.0%} ({kc.mastery_level})"
            )
        return "\n".join(lines)
