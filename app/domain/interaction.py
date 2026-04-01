"""
Öğrenci etkileşim event'leri — her soru/cevap döngüsünün kaydı.
Bu objeler embed edilerek pgvector'a yazılır.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class InteractionType(StrEnum):
    QUESTION = "question"            # öğrenci soru sordu
    EXPLANATION_GIVEN = "explanation_given"  # sistem açıklama yaptı
    MISCONCEPTION = "misconception"  # hata tespit edildi
    SUCCESS = "success"              # doğru cevap / kavrama
    STRUGGLE = "struggle"            # tekrarlayan yanlış / takılma
    HINT_REQUESTED = "hint_requested"


@dataclass
class Interaction:
    """Bir etkileşim olayı — hem DB'ye yazılır hem KT modelini besler."""

    learner_id: uuid.UUID
    session_id: uuid.UUID
    interaction_type: InteractionType
    content_summary: str             # embed edilecek kısa özet
    kc_tags: list[str] = field(default_factory=list)
    correctness: bool | None = None  # KT için — True/False/None
    full_text: str = ""              # tam metin (embed edilmez, log için)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_embed_text(self) -> str:
        """Embedding için kullanılacak metin."""
        kc_str = ", ".join(self.kc_tags) if self.kc_tags else "genel"
        return f"[{self.interaction_type}] Konu: {kc_str}. {self.content_summary}"


@dataclass
class Misconception:
    """Tespit edilen bir kavram yanılgısı."""

    learner_id: uuid.UUID
    kc_id: str
    description: str
    resolved: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
