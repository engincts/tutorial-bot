"""JSON config loader — Pydantic Settings custom source.

Priority (highest → lowest):
  1. Environment variables  (secrets: API keys, DB password)
  2. config.json            (non-secret settings)
  3. Field defaults
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class JsonConfigSource(PydanticBaseSettingsSource):
    """Reads config.json and flattens nested keys to Settings field names."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not CONFIG_PATH.exists():
            return {}
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return {
            # app
            "app_env":   raw.get("app", {}).get("env"),
            "log_level": raw.get("app", {}).get("log_level"),
            # llm
            "llm_provider":     raw.get("llm", {}).get("provider"),
            "openai_model":     raw.get("llm", {}).get("openai_model"),
            "anthropic_model":  raw.get("llm", {}).get("anthropic_model"),
            "novita_llm_model": raw.get("llm", {}).get("novita_model"),
            # embedder
            "embedder_provider":      raw.get("embedder", {}).get("provider"),
            "embedder_model":         raw.get("embedder", {}).get("model"),
            "openai_embedding_model": raw.get("embedder", {}).get("openai_model"),
            "novita_embedding_model": raw.get("embedder", {}).get("novita_model"),
            "embedding_dim":          raw.get("embedder", {}).get("dim"),
            # redis
            "redis_url":            raw.get("redis", {}).get("url"),
            "session_ttl_seconds":  raw.get("redis", {}).get("session_ttl_seconds"),
            # knowledge tracing
            "kt_model":      raw.get("knowledge_tracing", {}).get("model"),
            "kt_model_path": raw.get("knowledge_tracing", {}).get("model_path"),
            # retrieval
            "content_top_k":  raw.get("retrieval", {}).get("content_top_k"),
            "memory_top_k":   raw.get("retrieval", {}).get("memory_top_k"),
            "rerank_enabled": raw.get("retrieval", {}).get("rerank_enabled"),
            # pedagogy
            "mastery_threshold_low":  raw.get("pedagogy", {}).get("mastery_threshold_low"),
            "mastery_threshold_high": raw.get("pedagogy", {}).get("mastery_threshold_high"),
        }

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        value = self._data.get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {k: v for k, v in self._data.items() if v is not None}
