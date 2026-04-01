"""
Yanılgı kataloğu — tespit edilen misconception'ları yönetir.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interaction import Misconception
from app.services.learner_memory.profile_retriever import MisconductORM


class MisconceptionStore:

    async def add(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        kc_id: str,
        description: str,
    ) -> Misconception:
        """Yeni bir misconception kaydeder."""
        row = MisconductORM(
            id=uuid.uuid4(),
            learner_id=learner_id,
            kc_id=kc_id,
            description=description,
            resolved=False,
            detected_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.flush()
        return Misconception(
            id=row.id,
            learner_id=learner_id,
            kc_id=kc_id,
            description=description,
        )

    async def get_unresolved(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        kc_ids: list[str] | None = None,
    ) -> list[Misconception]:
        """Çözülmemiş yanılgıları getirir."""
        stmt = select(MisconductORM).where(
            MisconductORM.learner_id == learner_id,
            MisconductORM.resolved == False,  # noqa: E712
        )
        if kc_ids:
            stmt = stmt.where(MisconductORM.kc_id.in_(kc_ids))

        result = await session.execute(stmt)
        return [
            Misconception(
                id=row.id,
                learner_id=row.learner_id,
                kc_id=row.kc_id,
                description=row.description,
                resolved=row.resolved,
                detected_at=row.detected_at,
            )
            for row in result.scalars().all()
        ]

    async def resolve(
        self,
        session: AsyncSession,
        misconception_id: uuid.UUID,
    ) -> None:
        """Bir yanılgıyı çözümlendi olarak işaretle."""
        await session.execute(
            text("UPDATE misconceptions SET resolved = true WHERE id = :mid")
            .bindparams(mid=str(misconception_id))
        )

    def to_prompt_context(self, misconceptions: list[Misconception]) -> str:
        if not misconceptions:
            return ""
        lines = ["Dikkat edilmesi gereken kavram yanılgıları:"]
        for m in misconceptions:
            lines.append(f"- [{m.kc_id}] {m.description}")
        return "\n".join(lines)
