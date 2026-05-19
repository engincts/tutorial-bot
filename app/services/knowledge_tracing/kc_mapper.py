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
Görevin: Kullanıcı mesajındaki akademik konuyu JSON array olarak döndürmek.

ÇIKTI KURALI: Yanıtın yalnızca bir JSON array olacak. Başka hiçbir şey yazma. Açıklama yok, markdown yok, kod bloğu yok.

KC ID formatı: {ders}_{konu}_{kavram}
- Küçük harf, Türkçe karakter yok (ü→u, ş→s, ğ→g, ç→c, ı→i, ö→o), kelimeler arası alt çizgi
- ders örnekleri: matematik, fizik, kimya, biyoloji, turkce, tarih, cografya, felsefe
- konu örnekleri: turev, integral, kuvvet, asit_baz, hucre, sozcuk_turleri, osmanlı_tarihi
- kavram örnekleri: tanim, uygulama, zincir_kurali, sifat, zarf, isim_fiil

Sistemde yüklü dersler (varsa bunları ön planda tut): {course_names}

Örnekler:
- "Türev nedir?" → ["matematik_turev_tanim"]
- "sessiz kelimesi sıfat mı zarf mı?" → ["turkce_sozcuk_turleri_sifat_zarf"]
- "isim fiil nedir?" → ["turkce_fiilimsi_isim_fiil"]
- "Newton'un 2. yasası" → ["fizik_kuvvet_newton_2_kanun"]
- "merhaba nasılsın" → []

Akademik konu varsa mutlaka en az bir etiket üret.
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
                max_tokens=200,
            )
            raw = response.content.strip()
            logger.info("KC Mapper Raw Output: %r", raw)
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
            logger.error("KC extraction başarısız: %s", exc)
            return []
