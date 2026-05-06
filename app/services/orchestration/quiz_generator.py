from __future__ import annotations
import json
import logging
import re
from uuid import UUID

from app.infrastructure.llm.base import BaseLLMClient, Message
from app.domain.quiz import QuizQuestion

logger = logging.getLogger(__name__)

_GENERATE_SYSTEM = """\
Sen bir eğitim uzmanısın. Öğrencinin test edilmesi için verilen konuya (Knowledge Component) ve o konunun sağlanan içeriklerine (RAG dokümanları) dayanarak tek bir çoktan seçmeli soru üret.
Sorunun zorluğu orta seviye olmalı ve 4 şık (A, B, C, D) içermelidir.

Lütfen cevabı aşağıdaki JSON formatında döndür:
{
  "question": "Soru metni",
  "options": ["Şık 1", "Şık 2", "Şık 3", "Şık 4"],
  "correct_answer": "Doğru olan şıkkın TAM metni",
  "explanation": "Neden bu şıkkın doğru olduğuna dair kısa bir açıklama"
}
"""

class QuizGenerator:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def generate_question(self, kc_id: str, context: str) -> QuizQuestion | None:
        user_content = f"Konu (KC): {kc_id}\n\nİlgili İçerik:\n{context}"
        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_GENERATE_SYSTEM),
                    Message(role="user", content=user_content),
                ],
                temperature=0.7,
                max_tokens=300,
            )
            raw = response.content.strip()
            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if not match:
                return None
                
            data = json.loads(match.group())
            return QuizQuestion(
                question_text=data["question"],
                options=data["options"],
                correct_answer=data["correct_answer"],
                explanation=data["explanation"],
            )
        except Exception as exc:
            logger.error("Quiz question generation failed: %s", exc)
            return None
