"""POST /chat  &  POST /chat/stream (SSE)"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_orchestrator, get_chat_store
from app.api.dependencies_auth import get_current_learner_id
from app.infrastructure.chat_store import ChatStore
from app.infrastructure.database import get_session
from app.api.middleware.rate_limit import rate_limit_dependency
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
    mastery_subjects: dict[str, str]
    retrieved_sources: list[dict]
    model: str
    input_tokens: int
    output_tokens: int


@router.post("", response_model=ChatOut, dependencies=[Depends(rate_limit_dependency(60, 60))])
async def chat(
    body: ChatIn,
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    store: ChatStore = Depends(get_chat_store),
    db: AsyncSession = Depends(get_session),
) -> ChatOut:
    session_id = body.session_id or uuid.uuid4()

    title = body.message[:60].strip() or "Yeni Sohbet"
    await store.ensure_session(db, session_id, learner_id, title)
    await store.add_message(db, session_id, learner_id, "user", body.message)

    try:
        response = await orchestrator.chat(
            request=ChatRequest(
                learner_id=learner_id,
                session_id=session_id,
                message=body.message,
            ),
            db_session=db,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    await store.add_message(db, session_id, learner_id, "assistant", response.content)

    return ChatOut(
        content=response.content,
        session_id=response.session_id,
        kc_ids=response.kc_ids,
        mastery_snapshot=response.mastery_snapshot,
        mastery_subjects=response.mastery_subjects,
        retrieved_sources=response.retrieved_sources,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


@router.post("/stream", dependencies=[Depends(rate_limit_dependency(60, 60))])
async def chat_stream(
    body: ChatIn,
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    store: ChatStore = Depends(get_chat_store),
    db: AsyncSession = Depends(get_session),
):
    """SSE streaming — token token yanıt döner."""
    session_id = body.session_id or uuid.uuid4()

    title = body.message[:60].strip() or "Yeni Sohbet"
    await store.ensure_session(db, session_id, learner_id, title)
    await store.add_message(db, session_id, learner_id, "user", body.message)

    async def event_generator():
        try:
            full_content = ""
            async for event in orchestrator.chat_stream(
                request=ChatRequest(
                    learner_id=learner_id,
                    session_id=session_id,
                    message=body.message,
                ),
                db_session=db,
            ):
                if event["type"] == "token":
                    full_content += event["content"]
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "metadata":
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "done":
                    yield f"data: {json.dumps(event)}\n\n"

            await store.add_message(db, session_id, learner_id, "assistant", full_content)
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
