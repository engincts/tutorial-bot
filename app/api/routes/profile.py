"""GET /profile/{learner_id}"""
from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
        preferred_language=profile.preferred_language,
        preferences=profile.preferences,
        mastery_by_subject=dict(grouped),
    )
