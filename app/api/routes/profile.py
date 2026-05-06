"""GET /profile/{learner_id}"""
from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.dependencies import get_profile_retriever
from app.infrastructure.database import get_session
from app.services.learner_memory.profile_retriever import ProfileRetriever

router = APIRouter(prefix="/profile", tags=["profile"])


class KCMasteryOut(BaseModel):
    kc_id: str
    label: str
    p_mastery: float
    attempts: int


class ProfileOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    preferred_language: str
    preferences: dict
    mastery_by_subject: dict[str, list[KCMasteryOut]]


def _format_subject(raw: str) -> str:
    """'tyt_matematik' → 'TYT Matematik'"""
    return raw.replace("_", " ").title()


@router.get("/{learner_id}", response_model=ProfileOut)
async def get_profile(
    learner_id: uuid.UUID,
    retriever: ProfileRetriever = Depends(get_profile_retriever),
    db: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await retriever.get_or_create(db, learner_id)
    snapshot = await retriever.load_mastery_snapshot(db, learner_id)

    grouped: dict[str, list[KCMasteryOut]] = defaultdict(list)
    for kc in sorted(snapshot.components.values(), key=lambda k: -k.p_mastery):
        subject_key = _format_subject(kc.domain)
        grouped[subject_key].append(
            KCMasteryOut(
                kc_id=kc.kc_id,
                label=kc.label,
                p_mastery=kc.p_mastery,
                attempts=kc.attempts,
            )
        )

    return ProfileOut(
        learner_id=profile.id,
        display_name=profile.display_name,
        preferences=profile.preferences,
        mastery_by_subject=dict(grouped),
    )

class ProfilePatch(BaseModel):
    display_name: str | None = None
    preferred_language: str | None = None
    preferences: dict | None = None

@router.patch("/{learner_id}", response_model=ProfileOut)
async def patch_profile(
    learner_id: uuid.UUID,
    body: ProfilePatch,
    retriever: ProfileRetriever = Depends(get_profile_retriever),
    db: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await retriever.get_or_create(db, learner_id)
    if body.display_name is not None:
        profile.display_name = body.display_name
    if body.preferred_language is not None:
        profile.preferred_language = body.preferred_language
    if body.preferences is not None:
        profile.preferences = body.preferences
    
    await db.commit()
    return await get_profile(learner_id, retriever, db)

@router.delete("/{learner_id}", status_code=204)
async def delete_profile(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    from app.settings import get_settings
    from supabase._async.client import create_client
    
    s = get_settings()
    admin_client = await create_client(s.supabase_url, s.supabase_service_key)
    
    # 1. Supabase'den Auth Kullanıcısını Sil (Admin Key Gerektirir)
    try:
        await admin_client.auth.admin.delete_user(str(learner_id))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Supabase user deletion failed: %s", e)
        # Auth bulunamasa bile yerel verileri silmeye devam et

    # 2. Yerel DB verilerini sil (cascade yoksa manuel silmek gerek)
    await db.execute(text("DELETE FROM student_errors WHERE learner_id = :lid").bindparams(lid=learner_id))
    await db.execute(text("DELETE FROM chat_history WHERE learner_id = :lid").bindparams(lid=learner_id))
    await db.execute(text("DELETE FROM mastery_scores WHERE learner_id = :lid").bindparams(lid=learner_id))
    await db.execute(text("DELETE FROM quiz_sessions WHERE learner_id = :lid").bindparams(lid=learner_id))
    await db.execute(text("DELETE FROM student_profiles WHERE id = :lid").bindparams(lid=learner_id))
    
    await db.commit()
    return None
