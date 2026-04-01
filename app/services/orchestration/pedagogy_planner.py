"""
Pedagogy Planner — mastery seviyesine göre öğretim stratejisi seçer.
prompts/ klasöründeki .md şablonlarını yükler.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.knowledge_component import KCMasterySnapshot, MasteryLevel
from app.settings import Settings


class PedagogyPlanner:
    def __init__(self, settings: Settings, prompts_dir: str = "prompts") -> None:
        self._low_threshold = settings.mastery_threshold_low
        self._high_threshold = settings.mastery_threshold_high
        self._prompts_dir = Path(prompts_dir)
        self._cache: dict[str, str] = {}

    def _load_prompt(self, name: str) -> str:
        if name not in self._cache:
            path = self._prompts_dir / f"{name}.md"
            if path.exists():
                self._cache[name] = path.read_text(encoding="utf-8")
            else:
                self._cache[name] = ""
        return self._cache[name]

    def select_strategy(self, snapshot: KCMasterySnapshot) -> str:
        """
        Aktif KC'lerin ortalama mastery'sine göre strateji seçer.
        Dönen string prompt'a eklenir.
        """
        components = list(snapshot.components.values())
        if not components:
            return self._load_prompt("reinforcement")

        avg_mastery = sum(c.p_mastery for c in components) / len(components)

        if avg_mastery < self._low_threshold:
            return self._load_prompt("reinforcement")
        elif avg_mastery < self._high_threshold:
            return self._load_prompt("practice")
        else:
            return self._load_prompt("challenge")

    def mastery_level_for(self, snapshot: KCMasterySnapshot) -> MasteryLevel:
        components = list(snapshot.components.values())
        if not components:
            return MasteryLevel.UNKNOWN
        avg = sum(c.p_mastery for c in components) / len(components)
        if avg < self._low_threshold:
            return MasteryLevel.INTRODUCED
        elif avg < self._high_threshold:
            return MasteryLevel.PRACTICING
        return MasteryLevel.MASTERED
