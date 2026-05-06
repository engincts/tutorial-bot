"""
Prometheus metrics middleware — /metrics endpoint'i ve request/LLM metriklerini sağlar.
"""
from __future__ import annotations

import time
import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

# ── In-memory metric storage (lightweight, no prometheus_client dependency) ──

_metrics = {
    "http_requests_total": {},          # {method_path: count}
    "http_request_duration_seconds": {},  # {method_path: [sum, count]}
    "llm_tokens_total": {"input": 0, "output": 0},
    "worker_queue_depth": 0,
    "hallucination_alerts_total": 0,
    "dlq_size": 0,
}


def inc_request(method: str, path: str, status_code: int, duration: float) -> None:
    key = f'{method}_{path}_{status_code}'
    _metrics["http_requests_total"][key] = _metrics["http_requests_total"].get(key, 0) + 1
    if key not in _metrics["http_request_duration_seconds"]:
        _metrics["http_request_duration_seconds"][key] = [0.0, 0]
    _metrics["http_request_duration_seconds"][key][0] += duration
    _metrics["http_request_duration_seconds"][key][1] += 1


def inc_llm_tokens(input_tokens: int, output_tokens: int) -> None:
    _metrics["llm_tokens_total"]["input"] += input_tokens
    _metrics["llm_tokens_total"]["output"] += output_tokens


def set_queue_depth(depth: int) -> None:
    _metrics["worker_queue_depth"] = depth


def inc_hallucination_alert() -> None:
    _metrics["hallucination_alerts_total"] += 1


def set_dlq_size(size: int) -> None:
    _metrics["dlq_size"] = size


def _render_metrics() -> str:
    """Prometheus text format çıktısı üretir."""
    lines = []

    # Request counts
    lines.append("# HELP http_requests_total Total HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    for key, count in _metrics["http_requests_total"].items():
        parts = key.split("_", 2)
        method = parts[0]
        rest = "_".join(parts[1:])
        lines.append(f'http_requests_total{{method="{method}",path_status="{rest}"}} {count}')

    # Request duration
    lines.append("# HELP http_request_duration_seconds HTTP request latency")
    lines.append("# TYPE http_request_duration_seconds summary")
    for key, (total, count) in _metrics["http_request_duration_seconds"].items():
        avg = total / count if count > 0 else 0
        lines.append(f'http_request_duration_seconds_avg{{key="{key}"}} {avg:.4f}')
        lines.append(f'http_request_duration_seconds_count{{key="{key}"}} {count}')

    # LLM tokens
    lines.append("# HELP llm_tokens_total Total LLM tokens used")
    lines.append("# TYPE llm_tokens_total counter")
    lines.append(f'llm_tokens_total{{type="input"}} {_metrics["llm_tokens_total"]["input"]}')
    lines.append(f'llm_tokens_total{{type="output"}} {_metrics["llm_tokens_total"]["output"]}')

    # Queue depth
    lines.append("# HELP worker_queue_depth Current worker queue depth")
    lines.append("# TYPE worker_queue_depth gauge")
    lines.append(f'worker_queue_depth {_metrics["worker_queue_depth"]}')

    # Hallucination alerts
    lines.append("# HELP hallucination_alerts_total Total hallucination alerts")
    lines.append("# TYPE hallucination_alerts_total counter")
    lines.append(f'hallucination_alerts_total {_metrics["hallucination_alerts_total"]}')

    # DLQ size
    lines.append("# HELP dlq_size Current dead letter queue size")
    lines.append("# TYPE dlq_size gauge")
    lines.append(f'dlq_size {_metrics["dlq_size"]}')

    return "\n".join(lines) + "\n"


def setup_metrics(app: FastAPI) -> None:
    """FastAPI uygulamasına metrics middleware ve /metrics endpoint'i ekler."""

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        inc_request(request.method, request.url.path, response.status_code, duration)
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return PlainTextResponse(_render_metrics(), media_type="text/plain; version=0.0.4")
