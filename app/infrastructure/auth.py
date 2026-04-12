"""JWT token'dan learner_id okur — base64 decode, kütüphane bağımlılığı yok."""
from __future__ import annotations

import base64
import json
from uuid import UUID


def decode_token(token: str) -> UUID:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Geçersiz JWT formatı")
        # Base64url padding ekle
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return UUID(payload["sub"])
    except (KeyError, ValueError, Exception) as e:
        raise ValueError("Geçersiz token") from e
