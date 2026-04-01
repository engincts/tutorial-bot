"""
Standalone worker — ileride Celery/ARQ'ya geçiş için izole edilmiş.
Şu an main process içinde asyncio.create_task() ile kullanılıyor.
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Worker başlatıldı (standalone mod henüz implement edilmedi)")
    asyncio.run(asyncio.sleep(0))
