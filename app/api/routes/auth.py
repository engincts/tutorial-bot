"""POST /auth/register  POST /auth/login — Supabase Auth"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from supabase._async.client import AsyncClient, create_client

from app.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def _client() -> AsyncClient:
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
    client = await _client()
    try:
        response = await client.auth.sign_up({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not response.user:
        raise HTTPException(status_code=400, detail="Kayıt başarısız.")

    learner_id = uuid.UUID(response.user.id)
    token = response.session.access_token if response.session else ""
    return TokenOut(access_token=token, learner_id=learner_id)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn) -> TokenOut:
    client = await _client()
    try:
        response = await client.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı.")

    if not response.session:
        raise HTTPException(status_code=401, detail="Giriş başarısız.")

    learner_id = uuid.UUID(response.user.id)
    return TokenOut(access_token=response.session.access_token, learner_id=learner_id)
