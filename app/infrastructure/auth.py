"""JWT token'dan learner_id okur.

supabase_jwt_secret ayarlandıysa PyJWT ile imza doğrulaması yapılır.
Ayarlanmadıysa (development) sadece base64 decode ile payload okunur.
"""
from __future__ import annotations

import base64
import json
from uuid import UUID


def decode_token(token: str) -> UUID:
    try:
        from app.settings import get_settings
        secret = get_settings().supabase_jwt_secret

        if secret:
            import jwt as pyjwt
            payload = pyjwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        else:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Geçersiz JWT formatı")
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        return UUID(payload["sub"])
    except Exception as e:
        raise ValueError("Geçersiz token") from e
