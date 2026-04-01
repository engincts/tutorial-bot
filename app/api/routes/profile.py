"""GET /profile/{learner_id}"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_profile_retriever
from app.infrastructure.database import get_session
from app.services.learner_memory.profile_retriever import ProfileRetriever

router = APIRouter(prefix="/profile", tags=["profile"])


class KCMasteryOut(BaseModel):
    kc_id: str
    p_mastery: float
    attempts: int


class ProfileOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    preferred_language: str
    preferences: dict
    mastery: list[KCMasteryOut]


@router.get("/{learner_id}", response_model=ProfileOut)
async def get_profile(
    learner_id: uuid.UUID,
    retriever: ProfileRetriever = Depends(get_profile_retriever),
    db: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await retriever.get_or_create(db, learner_id)
    snapshot = await retriever.load_mastery_snapshot(db, learner_id)

    return ProfileOut(
        learner_id=profile.id,
        display_name=profile.display_name,
        preferred_language=profile.preferred_language,
        preferences=profile.preferences,
        mastery=[
            KCMasteryOut(kc_id=kc.kc_id, p_mastery=kc.p_mastery, attempts=kc.attempts)
            for kc in snapshot.components.values()
        ],
    )
