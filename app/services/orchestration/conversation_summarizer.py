"""
Conversation Summarizer — uzun sohbetlerde token tasarrufu için
geçmiş mesajları LLM ile özetler ve context window'u sıkıştırır.
"""
from __future__ import annotations

import logging

from app.infrastructure.llm.base import BaseLLMClient, Message

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM = """\
Sen bir eğitim asistanının konuşma geçmişini özetleyen bir araçsın.
Verilen konuşma geçmişini 3-5 cümleyle özetle. Özet:
- Öğrencinin sorduğu ana konuları
- Verilen önemli açıklamaları
- Tespit edilen eksiklikleri veya yanlış anlamaları
içermelidir. Türkçe yaz.
"""

# Eğer conversation history bu sayıdan fazla turn içeriyorsa özetle
SUMMARIZE_THRESHOLD = 10


class ConversationSummarizer:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def maybe_summarize(
        self,
        conversation_history: list[dict],
        threshold: int = SUMMARIZE_THRESHOLD,
    ) -> list[dict]:
        """
        Konuşma geçmişi threshold'u aşıyorsa eski kısmı özetler.
        Dönen liste: [{"role": "system", "content": "Önceki konuşma özeti: ..."}] + son N turn
        """
        if len(conversation_history) <= threshold:
            return conversation_history

        # Son 4 turn'u koru, gerisini özetle
        keep_recent = 4
        to_summarize = conversation_history[:-keep_recent]
        recent = conversation_history[-keep_recent:]

        summary_text = "\n".join(
            f"{turn['role'].upper()}: {turn['content'][:200]}"
            for turn in to_summarize
        )

        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_SUMMARY_SYSTEM),
                    Message(role="user", content=f"Konuşma geçmişi:\n{summary_text}"),
                ],
                temperature=0.3,
                max_tokens=300,
            )
            summary = response.content.strip()
        except Exception as exc:
            logger.warning("Conversation summarization failed: %s", exc)
            # Başarısızsa son N turn'u döndür
            return conversation_history[-threshold:]

        # Özeti bir system mesajı olarak ekle + son turn'ları koru
        summarized = [{"role": "system", "content": f"Önceki konuşma özeti:\n{summary}"}]
        summarized.extend(recent)

        logger.info(
            "Conversation summarized: %d turns → 1 summary + %d recent turns",
            len(to_summarize), len(recent),
        )
        return summarized
