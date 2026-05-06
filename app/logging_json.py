"""
Structured JSON logging — production ortamlarında ELK/Loki uyumlu log formatı sağlar.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Her log kaydını tek satır JSON olarak formatlar."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "learner_id"):
            log_entry["learner_id"] = record.learner_id
        if hasattr(record, "session_id"):
            log_entry["session_id"] = record.session_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        return json.dumps(log_entry, ensure_ascii=False)


def configure_json_logging(log_level: str = "INFO") -> None:
    """Production'da JSON formatında log kur."""
    json_fmt = JSONFormatter()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(json_fmt)

    root = logging.getLogger()
    root.setLevel(log_level.upper())
    root.handlers.clear()
    root.addHandler(console)

    # Gürültülü kütüphaneleri sustur
    for lib in ("httpx", "httpcore", "sqlalchemy.engine", "sqlalchemy.pool", "openai._base_client"):
        logging.getLogger(lib).setLevel(logging.WARNING)
