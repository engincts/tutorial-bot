"""
Session Manager — Redis üzerinde SessionContext yönetimi.
"""
from __future__ import annotations

import uuid

from app.domain.session_context import SessionContext
from app.infrastructure.redis_client import SessionCache


class SessionManager:
    def __init__(self, cache: SessionCache) -> None:
        self._cache = cache

    async def get_or_create(
        self,
        session_id: uuid.UUID,
        learner_id: uuid.UUID,
    ) -> SessionContext:
        data = await self._cache.get(str(session_id))
        if data:
            ctx = SessionContext.from_dict(data)
            if ctx.learner_id != learner_id:
                raise PermissionError(f"Session {session_id} bu kullanıcıya ait değil.")
            return ctx
        ctx = SessionContext(session_id=session_id, learner_id=learner_id)
        await self._cache.set(str(session_id), ctx.to_dict())
        return ctx

    async def save(self, ctx: SessionContext) -> None:
        await self._cache.set(str(ctx.session_id), ctx.to_dict())
        await self._cache.extend_ttl(str(ctx.session_id))

    async def reset(self, session_id: uuid.UUID) -> None:
        await self._cache.delete(str(session_id))
