"""Sohbet oturumu CRUD — GET/DELETE /conversations"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_store
from app.api.dependencies_auth import get_current_learner_id
from app.infrastructure.chat_store import ChatStore
from app.infrastructure.database import get_session

router = APIRouter(prefix="/conversations", tags=["conversations"])


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


@router.get("", response_model=list[SessionOut])
async def list_conversations(
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    store: ChatStore = Depends(get_chat_store),
    db: AsyncSession = Depends(get_session),
) -> list[SessionOut]:
    sessions = await store.list_sessions(db, learner_id)
    return [
        SessionOut(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: uuid.UUID,
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    store: ChatStore = Depends(get_chat_store),
    db: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    messages = await store.get_messages(db, session_id, learner_id=learner_id)
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/{session_id}", status_code=204)
async def delete_conversation(
    session_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_learner_id),
    store: ChatStore = Depends(get_chat_store),
    db: AsyncSession = Depends(get_session),
) -> None:
    await store.delete_session(db, session_id)
