"""POST /chat"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_orchestrator
from app.api.dependencies_auth import get_current_learner_id
from app.infrastructure.database import get_session
from app.services.orchestration.chat_orchestrator import ChatOrchestrator, ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    session_id: uuid.UUID | None = None
    message: str


class ChatOut(BaseModel):
    content: str
    session_id: uuid.UUID
    kc_ids: list[str]
    mastery_snapshot: dict[str, float]
    model: str
    input_tokens: int
    output_tokens: int


@router.post("", response_model=ChatOut)
async def chat(
    body: ChatIn,
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    session_id = body.session_id or uuid.uuid4()
    response = await orchestrator.chat(
        request=ChatRequest(
            learner_id=learner_id,
            session_id=session_id,
            message=body.message,
        ),
        db_session=db,
    )
    return ChatOut(
        content=response.content,
        session_id=response.session_id,
        kc_ids=response.kc_ids,
        mastery_snapshot=response.mastery_snapshot,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
