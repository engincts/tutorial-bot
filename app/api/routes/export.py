"""
Export API routes — öğrenci ilerlemesini CSV/JSON olarak indir.
"""
from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.infrastructure.database import get_session

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/mastery/{learner_id}/csv")
async def export_mastery_csv(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Öğrencinin mastery verilerini CSV olarak döner."""
    result = await db.execute(
        text("""
            SELECT kc_id, p_mastery, subject, attempts, updated_at
            FROM mastery_scores
            WHERE learner_id = :lid
            ORDER BY subject, kc_id
        """).bindparams(lid=learner_id)
    )
    rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["KC ID", "Mastery", "Ders", "Deneme Sayısı", "Son Güncelleme"])
    for r in rows:
        writer.writerow([r[0], f"{float(r[1]):.2f}", r[2] or "", r[3], str(r[4])])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mastery_{learner_id}.csv"},
    )


@router.get("/mastery/{learner_id}/json")
async def export_mastery_json(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Öğrencinin mastery verilerini JSON olarak döner."""
    result = await db.execute(
        text("""
            SELECT kc_id, p_mastery, subject, attempts, updated_at
            FROM mastery_scores
            WHERE learner_id = :lid
            ORDER BY subject, kc_id
        """).bindparams(lid=learner_id)
    )
    rows = result.fetchall()
    data = [
        {
            "kc_id": r[0],
            "mastery": float(r[1]),
            "subject": r[2] or "",
            "attempts": r[3],
            "updated_at": str(r[4]),
        }
        for r in rows
    ]
    return {"learner_id": str(learner_id), "mastery_data": data, "total_kcs": len(data)}


@router.get("/interactions/{learner_id}/csv")
async def export_interactions_csv(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    """Öğrencinin etkileşim geçmişini CSV olarak döner."""
    result = await db.execute(
        text("""
            SELECT interaction_type, content_summary, kc_tags, created_at
            FROM chat_history
            WHERE learner_id = :lid
            ORDER BY created_at DESC
            LIMIT 500
        """).bindparams(lid=learner_id)
    )
    rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tür", "Özet", "Kavramlar", "Tarih"])
    for r in rows:
        writer.writerow([r[0], r[1][:200], str(r[2] or []), str(r[3])])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=interactions_{learner_id}.csv"},
    )
