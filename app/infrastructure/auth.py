"""Supabase JWT verification via JWKS (ES256) with HS256 fallback."""
from __future__ import annotations

from functools import lru_cache
from uuid import UUID

import httpx
from jose import JWTError, jwt

from app.settings import get_settings


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    resp = httpx.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def decode_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            _get_jwks(),
            algorithms=["ES256", "HS256"],
            options={"verify_aud": False},
        )
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as e:
        raise ValueError("Geçersiz token") from e
