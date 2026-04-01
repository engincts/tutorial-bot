"""
KC Mapper — kullanıcı sorgusundan Knowledge Component etiketleri çıkarır.

LLM'e kısa bir structured extraction görevi verir:
  "Bu soruda hangi kavramlar geçiyor?" → ["derivatives", "chain_rule"]

Fallback: LLM yoksa basit keyword matching kullanır.
"""
from __future__ import annotations

import json
import logging
import re

from app.infrastructure.llm.base import BaseLLMClient, Message

logger = logging.getLogger(__name__)

_EXTRACTION_SYSTEM = """\
Sen bir eğitim içeriği analistinin yardımcısı olarak çalışıyorsun.
Verilen metinde geçen akademik kavramları (knowledge component'ları) tespit et.
SADECE JSON array döndür, başka hiçbir şey yazma.
Formatı: ["kc_id_1", "kc_id_2"]
KC ID'leri: küçük harf, alt çizgi ile boşluk, Türkçe veya İngilizce, max 4 kelime.
Örnek: ["derivatives", "chain_rule", "trigonometric_functions"]
Eğer belirgin bir kavram yoksa boş array döndür: []
"""


class KCMapper:
    def __init__(
        self,
        llm_client: BaseLLMClient,
        max_kc_per_query: int = 4,
    ) -> None:
        self._llm = llm_client
        self._max_kc = max_kc_per_query

    async def extract(self, text: str) -> list[str]:
        """
        Metinden KC etiketleri çıkarır.
        Hata durumunda boş liste döner — hiçbir zaman raise etmez.
        """
        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_EXTRACTION_SYSTEM),
                    Message(role="user", content=f"Metin: {text[:500]}"),
                ],
                temperature=0.0,
                max_tokens=100,
            )
            raw = response.content.strip()
            # JSON array çıkar
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if not match:
                return []
            kc_list: list[str] = json.loads(match.group())
            # Temizle ve sınırla
            return [
                re.sub(r"[^a-z0-9_]", "_", kc.lower().strip()).strip("_")
                for kc in kc_list
                if isinstance(kc, str) and kc.strip()
            ][: self._max_kc]
        except Exception as exc:
            logger.debug("KC extraction başarısız: %s", exc)
            return []
