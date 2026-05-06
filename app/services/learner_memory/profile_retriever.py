"""
Öğrenci profilini ve mastery snapshot'ını DB'den yükler.
Yeni öğrenci için default profil oluşturur.
"""
from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from datetime import datetime, timezone

from sqlalchemy import Text, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.knowledge_component import KCMasterySnapshot, KnowledgeComponent
from app.domain.learner_profile import LearnerProfile
from app.infrastructure.database import Base


# ── ORM Models (learner_profiles + kc_mastery) ────────────────────────────────

class LearnerProfileORM(Base):
    __tablename__ = "student_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_language: Mapped[str] = mapped_column(Text, server_default="tr")
    preferences: Mapped[str] = mapped_column(Text, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class KCMasteryORM(Base):
    __tablename__ = "mastery_scores"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kc_id: Mapped[str] = mapped_column(Text, primary_key=True)
    p_mastery: Mapped[float] = mapped_column(server_default="0.3")
    attempts: Mapped[int] = mapped_column(server_default="0")
    last_interaction: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)


class MisconductORM(Base):
    __tablename__ = "student_errors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kc_id: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(server_default="false")
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=False), server_default=text("NOW()")
    )


# ── Service ───────────────────────────────────────────────────────────────────

class ProfileRetriever:

    async def get_or_create(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        display_name: str = "Öğrenci",
    ) -> LearnerProfile:
        """Profili yükler, yoksa oluşturur."""
        row = await session.get(LearnerProfileORM, learner_id)
        if row is None:
            row = LearnerProfileORM(
                id=learner_id,
                display_name=display_name,
                preferred_language="tr",
                preferences="{}",
            )
            session.add(row)
            await session.flush()

        return LearnerProfile(
            id=row.id,
            display_name=row.display_name or display_name,
            preferred_language=row.preferred_language,
            preferences=json.loads(row.preferences or "{}"),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def save_preferences(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        preferences: dict,
    ) -> None:
        row = await session.get(LearnerProfileORM, learner_id)
        if row:
            row.preferences = json.dumps(preferences, ensure_ascii=False)
            row.updated_at = datetime.now(timezone.utc)
            await session.flush()

    async def load_mastery_snapshot(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        kc_ids: list[str] | None = None,
    ) -> KCMasterySnapshot:
        """
        Öğrencinin KC mastery durumlarını yükler.
        kc_ids verilirse sadece o KC'leri yükler.
        """
        stmt = select(KCMasteryORM).where(KCMasteryORM.learner_id == learner_id)
        if kc_ids:
            stmt = stmt.where(KCMasteryORM.kc_id.in_(kc_ids))

        result = await session.execute(stmt)
        rows = result.scalars().all()

        snapshot = KCMasterySnapshot()
        for row in rows:
            snapshot.upsert(
                KnowledgeComponent(
                    kc_id=row.kc_id,
                    label=row.kc_id.replace("_", " ").title(),
                    p_mastery=row.p_mastery,
                    attempts=row.attempts,
                    domain=row.subject or "genel",
                )
            )
        return snapshot

    async def upsert_kc_mastery(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        kc_id: str,
        p_mastery: float,
        subject: str | None = None,
    ) -> None:
        """Tek bir KC'nin mastery değerini günceller (upsert)."""
        await session.execute(
            text("""
                INSERT INTO mastery_scores (learner_id, kc_id, p_mastery, attempts, last_interaction, subject)
                VALUES (CAST(:learner_id AS uuid), :kc_id, :p_mastery, 1, NOW(), :subject)
                ON CONFLICT (learner_id, kc_id)
                DO UPDATE SET
                    p_mastery = :p_mastery,
                    attempts = mastery_scores.attempts + 1,
                    last_interaction = NOW(),
                    subject = COALESCE(:subject, mastery_scores.subject)
            """).bindparams(
                learner_id=str(learner_id),
                kc_id=kc_id,
                p_mastery=p_mastery,
                subject=subject,
            )
        )
