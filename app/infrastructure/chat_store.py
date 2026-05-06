"""Chat session ve mesaj kalıcılığı."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ChatSessionORM(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="Yeni Sohbet")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ChatStore:
    async def ensure_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        learner_id: uuid.UUID,
        title: str,
    ) -> None:
        """Oturum yoksa oluştur, varsa updated_at güncelle."""
        await session.execute(
            text("""
                INSERT INTO chat_sessions (id, learner_id, title)
                VALUES (CAST(:id AS uuid), CAST(:learner_id AS uuid), :title)
                ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
            """).bindparams(
                id=str(session_id),
                learner_id=str(learner_id),
                title=title,
            )
        )

    async def add_message(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        learner_id: uuid.UUID,
        role: str,
        content: str,
    ) -> None:
        msg = ChatMessageORM(
            id=uuid.uuid4(),
            session_id=session_id,
            learner_id=learner_id,
            role=role,
            content=content,
        )
        session.add(msg)
        await session.flush()

    async def list_sessions(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
    ) -> list[ChatSessionORM]:
        result = await session.execute(
            select(ChatSessionORM)
            .where(ChatSessionORM.learner_id == learner_id)
            .order_by(ChatSessionORM.updated_at.desc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def get_messages(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        learner_id: uuid.UUID | None = None,
    ) -> list[ChatMessageORM]:
        stmt = (
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at.asc())
        )
        if learner_id is not None:
            stmt = stmt.where(ChatMessageORM.learner_id == learner_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
    ) -> None:
        await session.execute(
            text("DELETE FROM chat_sessions WHERE id = CAST(:id AS uuid)").bindparams(
                id=str(session_id)
            )
        )
