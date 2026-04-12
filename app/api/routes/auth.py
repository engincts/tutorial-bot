"""POST /auth/register  POST /auth/login — Supabase Auth"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from supabase._async.client import AsyncClient, create_client

from app.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def _anon_client() -> AsyncClient:
    """Kullanıcı işlemleri (login) için anon key kullanılır."""
    s = get_settings()
    return await create_client(s.supabase_url, s.supabase_anon_key)


async def _admin_client() -> AsyncClient:
    """Admin işlemleri (register) için service key kullanılır."""
    s = get_settings()
    return await create_client(s.supabase_url, s.supabase_service_key)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    learner_id: uuid.UUID


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn) -> TokenOut:
    client = await _admin_client()
    try:
        res = await client.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not res.user:
        raise HTTPException(status_code=400, detail="Kayıt başarısız.")

    # Hemen login yap — token al
    anon = await _anon_client()
    try:
        sign_in = await anon.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TokenOut(
        access_token=sign_in.session.access_token,
        learner_id=uuid.UUID(res.user.id),
    )


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn) -> TokenOut:
    client = await _anon_client()
    try:
        res = await client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Giriş başarısız: {e}")

    if not res.session:
        raise HTTPException(status_code=401, detail="Giriş başarısız.")

    return TokenOut(
        access_token=res.session.access_token,
        learner_id=uuid.UUID(res.user.id),
    )
