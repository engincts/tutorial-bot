"""
Correctness Evaluator — öğrencinin mesajından doğruluk sinyali üretir.

Orchestrator LLM yanıtını ürettikten sonra bu sınıfı çağırır.
KT modeline `correct: bool` sinyali göndermek için kullanılır.

Dönüş:
  True  — öğrenci konuyu anlıyor
  False — öğrenci yanılıyor veya karışık
  None  — belirsiz (yeni soru, ilk mesaj vb.) → KT güncellenmez
"""
from __future__ import annotations

import json
import logging
import re

from app.infrastructure.llm.base import BaseLLMClient, Message

logger = logging.getLogger(__name__)

_SYSTEM = """\
Sen bir eğitim değerlendirme asistanısın.
Öğrencinin mesajını ve eğitmenin yanıtını analiz et.
Öğrencinin o konuyu anlayıp anlamadığını belirle.

SADECE JSON döndür, başka hiçbir şey yazma:
- Öğrenci doğru anlıyor/anladı → {"correct": true}
- Öğrenci yanlış anlıyor/yanılıyor → {"correct": false}
- Öğrenci yeni soru soruyor veya değerlendirme yapılamıyor → {"correct": null}
"""


class CorrectnessEvaluator:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def evaluate(
        self,
        user_message: str,
        assistant_response: str,
        kc_ids: list[str],
    ) -> bool | None:
        """
        Öğrencinin mesajını değerlendirir.
        Hata durumunda None döner, exception raise etmez.
        """
        if not kc_ids:
            return None

        kc_context = ", ".join(kc_ids[:4])
        user_content = (
            f"Konu alanları: {kc_context}\n\n"
            f"Öğrenci mesajı: {user_message[:400]}\n\n"
            f"Eğitmen yanıtı: {assistant_response[:400]}"
        )

        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_SYSTEM),
                    Message(role="user", content=user_content),
                ],
                temperature=0.0,
                max_tokens=20,
            )
            raw = response.content.strip()
            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            value = data.get("correct")
            if value is None:
                return None
            return bool(value)
        except Exception as exc:
            logger.debug("Correctness evaluation başarısız: %s", exc)
            return None
