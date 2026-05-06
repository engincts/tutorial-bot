"""
Prompt Builder — tüm context parçalarını tek bir LLM prompt'una birleştirir.

Bölüm sırası:
  1. system_base.md  (sabit sistem direktifi)
  2. Pedagoji stratejisi (mastery'ye göre)
  3. Öğrenci profili
  4. Mastery snapshot
  5. Kavram yanılgıları
  6. Benzer geçmiş etkileşimler (learner memory RAG)
  7. İlgili kaynak içeriği (content RAG)
  8. Konuşma geçmişi
"""
from __future__ import annotations

from pathlib import Path

from app.domain.interaction import Misconception
from app.domain.learner_profile import LearnerProfile
from app.domain.knowledge_component import KCMasterySnapshot
from app.infrastructure.llm.base import Message
from app.infrastructure.pg_vector_store import InteractionEmbedding
from app.services.content_rag.retriever import RetrievedChunk


class PromptBuilder:
    def __init__(self, prompts_dir: str = "prompts", summarizer=None) -> None:
        self._prompts_dir = Path(prompts_dir)
        self._system_base: str | None = None
        self._summarizer = summarizer

    def _get_system_base(self) -> str:
        if self._system_base is None:
            path = self._prompts_dir / "system_base.md"
            self._system_base = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._system_base

    async def build(
        self,
        user_query: str,
        profile: LearnerProfile,
        mastery_snapshot: KCMasterySnapshot,
        pedagogy_directive: str,
        content_chunks: list[RetrievedChunk],
        memory_interactions: list[InteractionEmbedding],
        misconceptions: list[Misconception],
        conversation_history: list[dict],
    ) -> list[Message]:
        """
        Tüm parçaları birleştirip Message listesi döner.
        LLM client bu listeyi doğrudan kullanır.
        """
        system_parts: list[str] = []

        # 1. Temel sistem direktifi
        base = self._get_system_base()
        if base:
            system_parts.append(base)

        # 2. Pedagoji stratejisi
        if pedagogy_directive.strip():
            system_parts.append(pedagogy_directive)

        # 3. Öğrenci profili
        profile_ctx = profile.to_prompt_context()
        if profile_ctx:
            system_parts.append(f"## Öğrenci Profili\n{profile_ctx}")

        # 4. Mastery snapshot
        mastery_ctx = mastery_snapshot.to_prompt_context()
        if mastery_ctx and mastery_ctx != "Henüz bilinen konu yok.":
            system_parts.append(f"## Konu Hakimiyet Durumu\n{mastery_ctx}")

        # 5. Kavram yanılgıları
        if misconceptions:
            misc_lines = ["## Dikkat Edilmesi Gereken Yanılgılar"]
            for m in misconceptions:
                misc_lines.append(f"- [{m.kc_id}] {m.description}")
            system_parts.append("\n".join(misc_lines))

        # 6. Benzer geçmiş etkileşimler
        if memory_interactions:
            mem_lines = ["## Benzer Geçmiş Etkileşimler"]
            for interaction in memory_interactions[:3]:
                mem_lines.append(f"- {interaction.content_summary}")
            system_parts.append("\n".join(mem_lines))

        # 7. İlgili kaynak içeriği
        if content_chunks:
            content_lines = ["## İlgili Kaynak İçeriği"]
            for i, chunk in enumerate(content_chunks, 1):
                heading = f"[{chunk.heading}] " if chunk.heading else ""
                content_lines.append(f"\n--- Kaynak {i} ---\n{heading}{chunk.content}")
            system_parts.append("\n".join(content_lines))

        system_prompt = "\n\n---\n\n".join(system_parts)

        messages: list[Message] = [Message(role="system", content=system_prompt)]

        # 8. Konuşma geçmişi (uzunsa özetle)
        if self._summarizer and len(conversation_history) > 10:
            conversation_history = await self._summarizer.maybe_summarize(conversation_history)

        for turn in conversation_history:
            messages.append(Message(role=turn["role"], content=turn["content"]))

        # 9. Güncel kullanıcı sorusu
        messages.append(Message(role="user", content=user_query))

        return messages
