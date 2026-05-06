"""
i18n — Öğrenci diline göre sistem prompt'larını seçer.
Desteklenen diller: tr (Türkçe - varsayılan), en (İngilizce).
"""
from __future__ import annotations

from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_TRANSLATIONS = {
    "tr": {
        "system_role": "Sen bir yapay zeka eğitim asistanısın.",
        "mastery_section": "Konu Hakimiyet Durumu",
        "misconception_section": "Dikkat Edilmesi Gereken Yanılgılar",
        "memory_section": "Benzer Geçmiş Etkileşimler",
        "source_section": "İlgili Kaynak İçeriği",
        "profile_section": "Öğrenci Profili",
        "quiz_generate_fail": "Soru üretilemedi.",
        "quiz_not_found": "Quiz bulunamadı.",
        "question_not_found": "Soru bulunamadı.",
        "prerequisite_warning": "DİKKAT: Öğrencinin bu konu ({kc_id}) için önkoşul olan '{prereq}' konusunda eksiği var.",
    },
    "en": {
        "system_role": "You are an AI teaching assistant.",
        "mastery_section": "Topic Mastery Status",
        "misconception_section": "Known Misconceptions",
        "memory_section": "Similar Past Interactions",
        "source_section": "Relevant Source Content",
        "profile_section": "Student Profile",
        "quiz_generate_fail": "Could not generate a question.",
        "quiz_not_found": "Quiz not found.",
        "question_not_found": "Question not found.",
        "prerequisite_warning": "NOTE: Student has a gap in prerequisite '{prereq}' for topic ({kc_id}).",
    },
}


def get_translation(lang: str, key: str, **kwargs) -> str:
    """Verilen dil ve anahtar için çeviri döner. Bulamazsa Türkçe fallback."""
    lang = lang.lower()[:2] if lang else "tr"
    translations = _TRANSLATIONS.get(lang, _TRANSLATIONS["tr"])
    template = translations.get(key, _TRANSLATIONS["tr"].get(key, key))
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def get_supported_languages() -> list[str]:
    """Desteklenen dil kodlarını döner."""
    return list(_TRANSLATIONS.keys())
