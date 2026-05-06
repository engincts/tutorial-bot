"""Centralized logging configuration — console + rotating file, per-service."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_NOISY_LIBS = (
    "httpx",
    "httpcore",
    "sqlalchemy.engine",
    "sqlalchemy.pool",
    "openai._base_client",
)


def configure_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    service: str = "api",  # "api" | "worker"
) -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    # Service-specific log: logs/api.log veya logs/worker.log
    service_handler = logging.handlers.RotatingFileHandler(
        filename=f"{log_dir}/{service}.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    service_handler.setFormatter(fmt)

    # Hata logu: tüm servislerden ERROR+ aynı dosyaya
    error_handler = logging.handlers.RotatingFileHandler(
        filename=f"{log_dir}/error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(log_level.upper())
    root.addHandler(console)
    root.addHandler(service_handler)
    root.addHandler(error_handler)

    for lib in _NOISY_LIBS:
        logging.getLogger(lib).setLevel(logging.WARNING)
