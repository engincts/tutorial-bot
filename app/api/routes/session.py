"""POST /session/reset"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_session_manager
from app.services.orchestration.session_manager import SessionManager

router = APIRouter(prefix="/session", tags=["session"])


class ResetOut(BaseModel):
    session_id: uuid.UUID
    reset: bool


@router.post("/reset", response_model=ResetOut)
async def reset_session(
    session_id: uuid.UUID,
    manager: SessionManager = Depends(get_session_manager),
) -> ResetOut:
    await manager.reset(session_id)
    return ResetOut(session_id=session_id, reset=True)
