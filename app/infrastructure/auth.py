"""JWT token'dan learner_id okur.

Supabase ES256 (yeni) ve HS256 (eski) tokenlarını destekler.
İmza doğrulaması yerine iss + exp claim'leri kontrol edilir.
"""
from __future__ import annotations

import time
from uuid import UUID

import jwt as pyjwt


def decode_token(token: str) -> UUID:
    from app.settings import get_settings
    try:
        settings = get_settings()

        payload = pyjwt.decode(
            token,
            key="",
            algorithms=["ES256", "HS256", "RS256"],
            options={"verify_signature": False},
        )

        exp = payload.get("exp", 0)
        if exp < time.time():
            raise ValueError("Token süresi dolmuş")

        if settings.supabase_url:
            expected_iss = f"{settings.supabase_url}/auth/v1"
            if payload.get("iss") != expected_iss:
                raise ValueError("Geçersiz token kaynağı")

        return UUID(payload["sub"])
    except Exception as e:
        raise ValueError("Geçersiz token") from e
