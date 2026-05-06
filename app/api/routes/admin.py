"""
Admin API routes — öğrenci listesi, mastery genel bakış, hallucination logları, DLQ yönetimi.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.infrastructure.database import get_session

router = APIRouter(prefix="/admin", tags=["admin"])


class LearnerSummary(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    avg_mastery: float
    total_interactions: int


class HallucinationLogOut(BaseModel):
    id: uuid.UUID
    learner_id: uuid.UUID
    session_id: uuid.UUID
    score: float
    assistant_response: str
    created_at: str


class DLQItem(BaseModel):
    index: int
    data: str


@router.get("/learners", response_model=list[LearnerSummary])
async def list_learners(db: AsyncSession = Depends(get_session)):
    """Tüm öğrencilerin özet bilgilerini döner."""
    result = await db.execute(text("""
        SELECT
            sp.id as learner_id,
            sp.display_name,
            COALESCE(AVG(ms.p_mastery), 0) as avg_mastery,
            COALESCE(COUNT(DISTINCT ch.id), 0) as total_interactions
        FROM student_profiles sp
        LEFT JOIN mastery_scores ms ON ms.learner_id = sp.id
        LEFT JOIN chat_history ch ON ch.learner_id = sp.id
        GROUP BY sp.id, sp.display_name
        ORDER BY sp.display_name
    """))
    rows = result.fetchall()
    return [
        LearnerSummary(
            learner_id=r[0], display_name=r[1] or "Anonim",
            avg_mastery=float(r[2]), total_interactions=int(r[3]),
        )
        for r in rows
    ]


@router.get("/learners/{learner_id}/mastery")
async def learner_mastery_detail(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Bir öğrencinin tüm konu bazlı mastery detayını döner."""
    result = await db.execute(
        text("""
            SELECT kc_id, p_mastery, subject, attempts, updated_at
            FROM mastery_scores
            WHERE learner_id = :lid
            ORDER BY subject, kc_id
        """).bindparams(lid=learner_id)
    )
    rows = result.fetchall()
    return [
        {
            "kc_id": r[0], "p_mastery": float(r[1]),
            "subject": r[2], "attempts": r[3],
            "updated_at": str(r[4]),
        }
        for r in rows
    ]


@router.get("/hallucination-logs", response_model=list[HallucinationLogOut])
async def get_hallucination_logs(
    limit: int = 50,
    min_score: float = 0.0,
    db: AsyncSession = Depends(get_session),
):
    """Hallucination loglarını listeler. min_score filtresi uygulanabilir."""
    result = await db.execute(
        text("""
            SELECT id, learner_id, session_id, score, assistant_response, created_at
            FROM hallucination_logs
            WHERE score >= :min_score
            ORDER BY created_at DESC
            LIMIT :limit
        """).bindparams(min_score=min_score, limit=limit)
    )
    rows = result.fetchall()
    return [
        HallucinationLogOut(
            id=r[0], learner_id=r[1], session_id=r[2],
            score=float(r[3]), assistant_response=r[4][:300],
            created_at=str(r[5]),
        )
        for r in rows
    ]


@router.get("/dlq")
async def get_dlq():
    """Dead letter queue içeriğini gösterir."""
    from app.infrastructure.redis_client import get_redis
    import json

    redis = get_redis()
    items = await redis.lrange("worker:memory_dlq", 0, -1)
    return [
        {"index": i, "data": item.decode() if isinstance(item, bytes) else str(item)}
        for i, item in enumerate(items)
    ]


@router.delete("/dlq")
async def clear_dlq():
    """Dead letter queue'yu temizler."""
    from app.infrastructure.redis_client import get_redis

    redis = get_redis()
    await redis.delete("worker:memory_dlq")
    return {"message": "DLQ temizlendi."}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_session)):
    """Genel istatistikler."""
    stats = {}

    r = await db.execute(text("SELECT COUNT(*) FROM student_profiles"))
    stats["total_learners"] = r.scalar()

    r = await db.execute(text("SELECT COUNT(*) FROM chat_history"))
    stats["total_interactions"] = r.scalar()

    r = await db.execute(text("SELECT COUNT(*) FROM quiz_sessions"))
    stats["total_quizzes"] = r.scalar()

    r = await db.execute(text("SELECT AVG(score) FROM hallucination_logs"))
    stats["avg_hallucination_score"] = float(r.scalar() or 0)

    r = await db.execute(text("SELECT COUNT(*) FROM mastery_scores"))
    stats["total_mastery_records"] = r.scalar()

    return stats
