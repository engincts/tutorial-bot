"""
LLM tabanlı bilgi seviyesi değerlendiricisi (Mastery Evaluator).
Kullanıcının etkileşimini (soru ve yanıt) değerlendirerek, her bir KC için 0.0 - 1.0 arasında yeni bir bilgi seviyesi (p_mastery) döner.
"""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from app.infrastructure.llm.base import BaseLLMClient, Message

logger = logging.getLogger(__name__)

_SYSTEM = """\
Sen bir eğitim uzmanı ve değerlendiricisin.
Öğrencinin mesajını ve eğitmenin yanıtını inceleyerek, öğrencinin konulardaki (knowledge components) bilgi seviyesini 0.0 ile 1.0 arasında bir değerle tahmin et.
- 0.0: Konu hakkında hiçbir fikri yok veya tamamen yanlış anlamış.
- 0.5: Konuya kısmen hakim ama eksikleri var.
- 1.0: Konuyu tamamen anlamış, uzman seviyesinde.

Değerlendirme sonucunu SADECE JSON formatında döndür.
Örnek Format:
{
  "matematik_turev_temel_kural": 0.8,
  "matematik_turev_zincir_kurali": 0.4
}

Başka hiçbir açıklama yazma.
"""

class LLMMasteryEvaluator:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def evaluate(
        self,
        user_message: str,
        assistant_response: str,
        kc_ids: list[str],
        current_mastery: dict[str, float] | None = None
    ) -> dict[str, float]:
        if not kc_ids:
            return {}

        current_mastery = current_mastery or {}
        context = []
        for kc in kc_ids:
            cur = current_mastery.get(kc, 0.3)
            context.append(f"- {kc} (Mevcut Seviye: {cur:.2f})")
        
        user_content = (
            f"Değerlendirilecek Konular:\n" + "\n".join(context) + "\n\n"
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
                max_tokens=100,
            )
            raw = response.content.strip()
            match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if not match:
                return {}
                
            data = json.loads(match.group())
            
            # Sadece istenen KC ID'ler için sonuçları al, değilse filtrele
            new_mastery = {}
            for kc in kc_ids:
                if kc in data and isinstance(data[kc], (int, float)):
                    new_mastery[kc] = max(0.0, min(1.0, float(data[kc])))
                    
            return new_mastery
        except Exception as exc:
            logger.debug("LLM mastery evaluation başarısız: %s", exc)
            return {}
