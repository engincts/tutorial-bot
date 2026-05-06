"""
Pedagogy Planner — mastery seviyesine göre öğretim stratejisi seçer.
prompts/ klasöründeki .md şablonlarını yükler.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.knowledge_component import KCMasterySnapshot, MasteryLevel
from app.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.prerequisite_store import PrerequisiteStore

class PedagogyPlanner:
    def __init__(self, settings: Settings, prerequisite_store: PrerequisiteStore | None = None, prompts_dir: str = "prompts") -> None:
        self._low_threshold = settings.mastery_threshold_low
        self._high_threshold = settings.mastery_threshold_high
        self._prompts_dir = Path(prompts_dir)
        self._prerequisite_store = prerequisite_store or PrerequisiteStore()
        self._cache: dict[str, str] = {}

    def _load_prompt(self, name: str) -> str:
        if name not in self._cache:
            path = self._prompts_dir / f"{name}.md"
            if path.exists():
                self._cache[name] = path.read_text(encoding="utf-8")
            else:
                self._cache[name] = ""
        return self._cache[name]

    async def select_strategy(self, snapshot: KCMasterySnapshot, session: AsyncSession | None = None) -> str:
        """
        Aktif KC'lerin ortalama mastery'sine göre strateji seçer.
        Eğer session verildiyse prerequisite (önkoşul) kontrolü yapar.
        Dönen string prompt'a eklenir.
        """
        components = list(snapshot.components.values())
        if not components:
            return self._load_prompt("reinforcement")

        # Prerequisite check
        if session:
            kc_ids = [c.kc_id for c in components]
            prereqs_map = await self._prerequisite_store.get_prerequisites(session, kc_ids)
            for kc_id, prereqs in prereqs_map.items():
                for pq in prereqs:
                    pq_kc = snapshot.components.get(pq)
                    if not pq_kc or pq_kc.p_mastery < self._low_threshold:
                        # Önkoşul eksik, önce önkoşulu öğret
                        return f"DİKKAT: Öğrencinin bu konu ({kc_id}) için önkoşul olan '{pq}' konusunda eksiği var. Lütfen açıklamaya öncelikle '{pq}' konusunun temelini atarak başla ve daha sonra ana soruya geç."

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
