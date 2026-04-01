"""
SessionContext — aktif bir konuşma oturumunun in-memory state'i.
Redis'e JSON olarak serialize edilir.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.knowledge_component import KCMasterySnapshot
from app.domain.learner_profile import LearnerProfile


@dataclass
class TurnRecord:
    """Tek bir konuşma turu (soru + cevap)."""
    role: str   # "user" | "assistant"
    content: str
    kc_tags: list[str] = field(default_factory=list)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class SessionContext:
    """
    Aktif oturum state'i — Redis'te yaşar.
    Her request'te yüklenir, her response'ta güncellenir.
    """

    session_id: uuid.UUID = field(default_factory=uuid.uuid4)
    learner_id: uuid.UUID = field(default_factory=uuid.uuid4)
    turns: list[TurnRecord] = field(default_factory=list)
    active_kc_ids: list[str] = field(default_factory=list)  # bu oturumda çalışılan KC'ler
    mastery_snapshot: KCMasterySnapshot = field(default_factory=KCMasterySnapshot)
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ── Turn management ───────────────────────────────────────────────

    def add_turn(self, role: str, content: str, kc_tags: list[str] | None = None) -> None:
        self.turns.append(TurnRecord(role=role, content=content, kc_tags=kc_tags or []))
        self.last_activity = datetime.now(timezone.utc)

    def recent_turns(self, n: int = 6) -> list[TurnRecord]:
        """Son N turu döner — prompt'a eklenecek konuşma geçmişi."""
        return self.turns[-n:]

    def to_conversation_history(self, n: int = 6) -> list[dict]:
        """LLM client formatında konuşma geçmişi."""
        return [
            {"role": t.role, "content": t.content}
            for t in self.recent_turns(n)
        ]

    # ── Serialization (Redis için) ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id": str(self.session_id),
            "learner_id": str(self.learner_id),
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "kc_tags": t.kc_tags,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in self.turns
            ],
            "active_kc_ids": self.active_kc_ids,
            "mastery_snapshot": {
                kc_id: {
                    "kc_id": kc.kc_id,
                    "label": kc.label,
                    "p_mastery": kc.p_mastery,
                    "attempts": kc.attempts,
                    "domain": kc.domain,
                }
                for kc_id, kc in self.mastery_snapshot.components.items()
            },
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionContext":
        from app.domain.knowledge_component import KnowledgeComponent

        mastery = KCMasterySnapshot()
        for kc_id, kc_data in data.get("mastery_snapshot", {}).items():
            mastery.upsert(KnowledgeComponent(**kc_data))

        ctx = cls(
            session_id=uuid.UUID(data["session_id"]),
            learner_id=uuid.UUID(data["learner_id"]),
            active_kc_ids=data.get("active_kc_ids", []),
            mastery_snapshot=mastery,
            started_at=datetime.fromisoformat(data["started_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
        )
        for t in data.get("turns", []):
            ctx.turns.append(
                TurnRecord(
                    role=t["role"],
                    content=t["content"],
                    kc_tags=t.get("kc_tags", []),
                    timestamp=datetime.fromisoformat(t["timestamp"]),
                )
            )
        return ctx
