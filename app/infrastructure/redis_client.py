import json
from typing import Any

import redis.asyncio as aioredis

from app.settings import Settings, get_settings

_redis: aioredis.Redis | None = None


def init_redis(settings: Settings | None = None) -> None:
    global _redis
    settings = settings or get_settings()
    _redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis başlatılmadı — init_redis() çağrılmamış.")
    return _redis


class SessionCache:
    """
    JSON-serializable dict'leri Redis'e yazar/okur.
    Key formatı: session:{session_id}
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = ttl_seconds or get_settings().session_ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def get(self, session_id: str) -> dict[str, Any] | None:
        raw = await get_redis().get(self._key(session_id))
        return json.loads(raw) if raw else None

    async def set(self, session_id: str, data: dict[str, Any]) -> None:
        await get_redis().setex(
            self._key(session_id),
            self._ttl,
            json.dumps(data, default=str),
        )

    async def delete(self, session_id: str) -> None:
        await get_redis().delete(self._key(session_id))

    async def extend_ttl(self, session_id: str) -> None:
        await get_redis().expire(self._key(session_id), self._ttl)


_WORKER_QUEUE_KEY = "worker:memory_queue"
_WORKER_DLQ_KEY = "worker:memory_dlq"
_DLQ_MAX_SIZE = 500


class WorkerQueue:
    """
    Redis list tabanlı iş kuyruğu.
    API: LPUSH (sol), Worker: BRPOP (sağ) — FIFO sırası.
    Başarısız job'lar push_dead() ile DLQ'ya taşınır.
    """

    async def push(self, job: dict) -> None:
        await get_redis().lpush(_WORKER_QUEUE_KEY, json.dumps(job, default=str))

    async def pop(self, timeout: int = 5) -> dict | None:
        result = await get_redis().brpop(_WORKER_QUEUE_KEY, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        return json.loads(raw)

    async def push_dead(self, job: dict, error: str) -> None:
        """Başarısız job'u DLQ'ya yazar. Liste _DLQ_MAX_SIZE ile sınırlandırılır."""
        import datetime
        entry = {**job, "_error": error, "_failed_at": datetime.datetime.utcnow().isoformat()}
        redis = get_redis()
        await redis.lpush(_WORKER_DLQ_KEY, json.dumps(entry, default=str))
        await redis.ltrim(_WORKER_DLQ_KEY, 0, _DLQ_MAX_SIZE - 1)
