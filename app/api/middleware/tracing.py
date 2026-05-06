"""
Request ID middleware — her isteğe benzersiz bir X-Request-ID atar.
OpenTelemetry-lite tracing desteği sağlar.
"""
from __future__ import annotations

import uuid
import logging
import contextvars
import time

from fastapi import FastAPI, Request, Response

# Context variable for request tracking
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

logger = logging.getLogger(__name__)


class RequestContextFilter(logging.Filter):
    """Log kayıtlarına request_id ekleyen filter."""
    def filter(self, record):
        record.request_id = request_id_var.get("")
        return True


def setup_tracing(app: FastAPI) -> None:
    """Request tracing middleware'ini uygulamaya ekler."""

    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next) -> Response:
        # Gelen header varsa onu kullan, yoksa yeni ID üret
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(req_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        logger.info(
            "request completed | method=%s path=%s status=%d duration=%.3fs request_id=%s",
            request.method, request.url.path, response.status_code, duration, req_id,
        )

        return response

    # Root logger'a request_id filter ekle
    root_logger = logging.getLogger()
    root_logger.addFilter(RequestContextFilter())
