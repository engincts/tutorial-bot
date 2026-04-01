"""
LearnerProfile — öğrencinin kalıcı profili.
DB satırına 1:1 karşılık gelir, aynı zamanda prompt context'i üretir.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LearnerProfile:
    """
    Öğrenci profili — DB'den yüklenir, oturum boyunca bellekte tutulur.
    """

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    display_name: str = "Öğrenci"
    preferred_language: str = "tr"
    # Öğrenme tercihleri (LLM tarafından çıkarılır ve güncellenir)
    preferences: dict = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ── Preferences helpers ───────────────────────────────────────────

    def get_preference(self, key: str, default=None):
        return self.preferences.get(key, default)

    def set_preference(self, key: str, value) -> None:
        self.preferences[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def to_prompt_context(self) -> str:
        """Prompt'a eklenecek profil özeti."""
        parts = [f"Öğrenci: {self.display_name}"]
        if explanation_style := self.preferences.get("explanation_style"):
            parts.append(f"Tercih ettiği açıklama stili: {explanation_style}")
        if pace := self.preferences.get("learning_pace"):
            parts.append(f"Öğrenme hızı: {pace}")
        if difficulties := self.preferences.get("known_difficulties"):
            parts.append(f"Bilinen zorluk alanları: {', '.join(difficulties)}")
        return "\n".join(parts)
