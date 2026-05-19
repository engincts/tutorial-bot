"""FastAPI dependency — JWT token'dan learner_id çıkarır."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.infrastructure.auth import decode_token

_bearer = HTTPBearer()


def get_current_learner_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    try:
        return decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    from app.settings import get_settings
    from app.infrastructure.database import SessionLocal
    from sqlalchemy import text
    import jwt as pyjwt

    try:
        learner_id = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")

    async with SessionLocal() as db:
        result = await db.execute(text("SELECT role FROM student_profiles WHERE id = :id").bindparams(id=str(learner_id)))
        role = result.scalar()

    if role != "admin":
        settings = get_settings()
        payload = pyjwt.decode(
            credentials.credentials,
            key="",
            algorithms=["ES256", "HS256", "RS256"],
            options={"verify_signature": False},
        )
        if payload.get("email") != settings.admin_email:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlemi yapmak için yönetici yetkiniz yok.")

    return learner_id
