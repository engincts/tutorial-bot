"""
Post-response worker — Redis kuyruğundan iş alır, memory günceller.

Akış:
  1. BRPOP ile kuyruktan job al
  2. Interaction objesi oluştur
  3. MemoryUpdater.update() çağır (embed + mastery + misconception)
  4. Başarısız olursa en fazla MAX_ATTEMPTS kez yeniden dene
  5. Tüm denemeler başarısız olursa job'u DLQ'ya taşı
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.domain.interaction import Interaction, InteractionType, Misconception
from app.infrastructure.database import init_db
from app.infrastructure.redis_client import WorkerQueue, init_redis
from app.logging_config import configure_logging
from app.settings import get_settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0  # saniye — her denemede 2x artar


async def _process(job: dict) -> None:
    from app.api.dependencies import get_memory_updater

    interaction = Interaction(
        learner_id=uuid.UUID(job["learner_id"]),
        session_id=uuid.UUID(job["session_id"]),
        interaction_type=InteractionType(job["interaction_type"]),
        content_summary=job["content_summary"],
        kc_tags=job.get("kc_tags") or [],
    )
    new_mastery: dict[str, float] | None = job.get("new_mastery")
    misconceptions = [
        Misconception(
            learner_id=interaction.learner_id,
            kc_id=m["kc_id"],
            description=m["description"],
        )
        for m in (job.get("misconceptions") or [])
    ]

    await get_memory_updater().update(
        interaction=interaction,
        new_mastery=new_mastery,
        misconceptions=misconceptions or None,
        subject=job.get("subject"),
        user_message=job.get("user_message"),
        assistant_response=job.get("assistant_response"),
        context_used=job.get("context_used")
    )
    logger.info(
        "job işlendi | learner=%s kc=%s mastery_updated=%s misconceptions=%d",
        job["learner_id"],
        job.get("kc_tags"),
        new_mastery is not None,
        len(misconceptions),
    )


async def _process_with_retry(job: dict, queue: WorkerQueue) -> None:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await _process(job)
            return
        except Exception as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "job başarısız (deneme %d/%d), %.0fs sonra yeniden — %s",
                    attempt, MAX_ATTEMPTS, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "job kalıcı olarak başarısız (deneme %d/%d) — DLQ'ya taşınıyor | %s",
                    attempt, MAX_ATTEMPTS, exc,
                )

    await queue.push_dead(job, str(last_error))


async def _run() -> None:
    settings = get_settings()
    configure_logging(log_level=settings.log_level, service="worker")
    init_db(settings)
    init_redis(settings)

    queue = WorkerQueue()
    logger.info("Worker başlatıldı — kuyruk dinleniyor: worker:memory_queue")

    while True:
        try:
            job = await queue.pop(timeout=5)
            if job:
                await _process_with_retry(job, queue)
        except Exception:
            logger.exception("Worker döngüsü hatası — devam ediliyor")


if __name__ == "__main__":
    asyncio.run(_run())
