"""
Event Bus — mastery değişimlerinde dış sistemlere bildirim gönderir.
Redis Pub/Sub tabanlı basit bir event sistemi.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CHANNEL_MASTERY_CHANGE = "events:mastery_change"
CHANNEL_QUIZ_COMPLETED = "events:quiz_completed"
CHANNEL_HALLUCINATION = "events:hallucination_detected"


@dataclass
class Event:
    event_type: str
    learner_id: str
    data: dict
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class EventBus:
    """Redis Pub/Sub tabanlı event yayıncısı."""

    async def publish(self, channel: str, event: Event) -> None:
        try:
            from app.infrastructure.redis_client import get_redis
            redis = get_redis()
            await redis.publish(channel, json.dumps(asdict(event)))
            logger.debug("Event published | channel=%s type=%s", channel, event.event_type)
        except Exception as exc:
            logger.warning("Event publish failed: %s", exc)

    async def publish_mastery_change(
        self, learner_id: uuid.UUID, kc_id: str, old_mastery: float, new_mastery: float
    ) -> None:
        event = Event(
            event_type="mastery_change",
            learner_id=str(learner_id),
            data={
                "kc_id": kc_id,
                "old_mastery": old_mastery,
                "new_mastery": new_mastery,
                "delta": new_mastery - old_mastery,
            },
        )
        await self.publish(CHANNEL_MASTERY_CHANGE, event)

    async def publish_quiz_completed(
        self, learner_id: uuid.UUID, quiz_id: uuid.UUID, score: float
    ) -> None:
        event = Event(
            event_type="quiz_completed",
            learner_id=str(learner_id),
            data={"quiz_id": str(quiz_id), "score": score},
        )
        await self.publish(CHANNEL_QUIZ_COMPLETED, event)

    async def publish_hallucination(
        self, learner_id: uuid.UUID, session_id: uuid.UUID, score: float
    ) -> None:
        event = Event(
            event_type="hallucination_detected",
            learner_id=str(learner_id),
            data={"session_id": str(session_id), "score": score},
        )
        await self.publish(CHANNEL_HALLUCINATION, event)
