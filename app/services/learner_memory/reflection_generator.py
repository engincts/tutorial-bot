import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infrastructure.llm.base import BaseLLMClient, Message
from app.infrastructure.database import get_session_factory
from app.infrastructure.pg_vector_store import InteractionEmbedding

logger = logging.getLogger(__name__)

_REFLECTION_SYSTEM = """\
Sen bir öğrenci danışmanısın. Öğrencinin son konuşmalarını ve etkinliklerini analiz edeceksin.
Öğrencinin anladığı ve güçlü olduğu konuları, zorlandığı veya eksik olduğu konuları özetle.
Sonuç olarak bana aşağıdaki JSON formatında kısa, maddeler halinde bir değerlendirme ver:
{
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "summary_note": "Genel bir yönlendirme veya not"
}
"""

class ReflectionGenerator:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def generate_reflection(self, session: AsyncSession, learner_id: UUID) -> dict | None:
        # Son 10 interaction'ı getir
        stmt = (
            select(InteractionEmbedding)
            .where(InteractionEmbedding.learner_id == learner_id)
            .order_by(InteractionEmbedding.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        interactions = list(result.scalars().all())

        if len(interactions) < 10:
            return None  # Yeterli veri yok

        # Eğer son interaction zaten REFLECTION ise tekrar yapma
        if interactions and interactions[0].interaction_type == "reflection":
            return None

        history_text = "\n".join([
            f"[{i.interaction_type}] (Kavramlar: {i.kc_tags}): {i.content_summary}"
            for i in reversed(interactions)
        ])

        try:
            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_REFLECTION_SYSTEM),
                    Message(role="user", content=f"Son etkileşimler:\n{history_text}"),
                ],
                temperature=0.5,
                max_tokens=300,
            )
            import re, json
            match = re.search(r"\{.*?\}", response.content.strip(), re.DOTALL)
            if not match:
                return None
                
            return json.loads(match.group())
        except Exception as exc:
            logger.error("Reflection generation failed: %s", exc)
            return None
