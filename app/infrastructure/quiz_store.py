from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import select, String, Float, DateTime, Text, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.domain.quiz import QuizSession, QuizQuestion

class QuizSessionORM(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kc_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default="active")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class QuizQuestionORM(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[str] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=True)


class QuizAnswerORM(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    learner_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))


class QuizStore:
    async def create_session(self, session: AsyncSession, quiz: QuizSession) -> QuizSessionORM:
        orm = QuizSessionORM(
            id=quiz.id,
            learner_id=quiz.learner_id,
            kc_id=quiz.kc_id,
            status=quiz.status,
            score=quiz.score,
        )
        session.add(orm)
        
        for q in quiz.questions:
            import json
            q_orm = QuizQuestionORM(
                id=q.id,
                quiz_id=quiz.id,
                question_text=q.question_text,
                options=json.dumps(q.options),
                correct_answer=q.correct_answer,
                explanation=q.explanation,
            )
            session.add(q_orm)
            
        await session.flush()
        return orm

    async def get_session(self, session: AsyncSession, quiz_id: uuid.UUID) -> QuizSessionORM | None:
        return await session.get(QuizSessionORM, quiz_id)

    async def get_question(self, session: AsyncSession, question_id: uuid.UUID) -> QuizQuestionORM | None:
        return await session.get(QuizQuestionORM, question_id)

    async def save_answer(
        self, session: AsyncSession, quiz_id: uuid.UUID, question_id: uuid.UUID, learner_answer: str, is_correct: bool
    ) -> None:
        ans = QuizAnswerORM(
            quiz_id=quiz_id,
            question_id=question_id,
            learner_answer=learner_answer,
            is_correct=is_correct,
        )
        session.add(ans)
        
        # update quiz score
        quiz = await session.get(QuizSessionORM, quiz_id)
        if quiz:
            quiz.status = "completed"
            quiz.score = 100.0 if is_correct else 0.0
            
        await session.flush()
