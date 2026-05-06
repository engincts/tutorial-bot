"""
Misconception Detector — öğrencinin mesajından kavram yanılgılarını tespit eder.

LLM'e kısa bir structured prompt gönderir:
  - Öğrencinin mesajı + asistan yanıtı + aktif KC listesi → yanılgı listesi
  - Yanılgı yoksa boş liste döner
  - Hata durumunda boş liste döner, exception raise etmez
"""
from __future__ import annotations

import json
import logging
import re

from app.infrastructure.llm.base import BaseLLMClient, Message

logger = logging.getLogger(__name__)

_SYSTEM = """\
Sen bir eğitim analisti olarak çalışıyorsun.
Öğrencinin mesajını incele ve açıkça yanlış olan kavramsal yanılgıları tespit et.

SADECE JSON döndür:
{
  "misconceptions": [
    {"kc_id": "kavram_adi", "description": "Yanılgının kısa açıklaması (max 100 karakter)"},
    ...
  ]
}

Yanılgı yoksa: {"misconceptions": []}

Kurallar:
- Sadece öğrencinin mesajındaki açık hataları raporla (asistan yanıtındakileri değil)
- KC ID: küçük harf, alt çizgi, max 4 kelime
- Her yanılgı için description Türkçe olsun
- Belirsiz/yorum gerektiren durumlarda yanılgı sayma
"""


class MisconceptionDetector:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def detect(
        self,
        user_message: str,
        assistant_response: str,
        kc_ids: list[str],
    ) -> list[tuple[str, str]]:
        """
        Öğrencinin mesajındaki yanılgıları tespit eder.
        Dönüş: [(kc_id, description), ...]
        Hata durumunda [] döner.
        """
        if not kc_ids or not user_message.strip():
            return []

        kc_context = ", ".join(kc_ids[:6])
        user_content = (
            f"Aktif konular: {kc_context}\n\n"
            f"Öğrenci mesajı: {user_message[:500]}\n\n"
            f"Eğitmen yanıtı (referans): {assistant_response[:300]}"
        )

        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_SYSTEM),
                    Message(role="user", content=user_content),
                ],
                temperature=0.0,
                max_tokens=300,
            )
            raw = response.content.strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())
            items = data.get("misconceptions", [])
            return [
                (item["kc_id"], item["description"])
                for item in items
                if isinstance(item, dict) and item.get("kc_id") and item.get("description")
            ]
        except Exception as exc:
            logger.debug("Misconception detection başarısız: %s", exc)
            return []
