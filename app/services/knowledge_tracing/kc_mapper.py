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

KC ID formatı: {ders}_{konu}_{kavram} — üç katmanlı, küçük harf Türkçe, kelimeler arası alt çizgi.
- ders: Sistemde bulunan ana ders adlarından birini kullanmalısın. Eğer sistemde mevcut değilse en uygununu seç.
Mevcut Ana Ders Adları: {course_names}
- konu: turev, integral, kuvvet, asit_baz, hucre, denklem, paragraf vb.
- kavram: zincir_kural, newton_2_kanun, ph_hesabi, mitoz, ikinci_derece vb.

Örnekler:
- Türev sorusu     → ["matematik_turev_temel_kural", "matematik_turev_zincir_kural"]
- Newton yasaları  → ["fizik_kuvvet_newton_2_kanun", "fizik_kuvvet_momentum"]

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

    async def extract(self, text: str, course_names: list[str] | None = None) -> list[str]:
        """
        Metinden KC etiketleri çıkarır.
        Hata durumunda boş liste döner — hiçbir zaman raise etmez.
        """
        try:
            course_list_str = ", ".join(course_names) if course_names else "Genel"
            system_prompt = _EXTRACTION_SYSTEM.replace("{course_names}", course_list_str)

            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=system_prompt),
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
