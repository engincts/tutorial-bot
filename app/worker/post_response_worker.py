"""
Standalone worker — ileride Celery/ARQ'ya geçiş için izole edilmiş.
Şu an main process içinde asyncio.create_task() ile kullanılıyor.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

async def _run() -> None:
    logger.info("Worker başlatıldı (standalone mod henüz implement edilmedi — idle bekliyor)")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(_run())
