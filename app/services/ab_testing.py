"""
A/B Test Altyapısı — farklı pedagoji stratejilerini karşılaştırma.
Öğrenciyi rastgele bir gruba atar ve o gruba uygun stratejiyi uygular.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Experiment:
    """Bir A/B test deneyini tanımlar."""
    id: str
    name: str
    variants: list[str] = field(default_factory=lambda: ["control", "treatment"])
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Aktif deneyler ──
_EXPERIMENTS: dict[str, Experiment] = {
    "pedagogy_strategy": Experiment(
        id="pedagogy_strategy",
        name="Pedagoji Stratejisi A/B Testi",
        variants=["standard", "socratic", "scaffolding"],
    ),
    "prompt_style": Experiment(
        id="prompt_style",
        name="Prompt Stili A/B Testi",
        variants=["concise", "detailed"],
    ),
}


def get_variant(experiment_id: str, learner_id: uuid.UUID) -> str:
    """
    Öğrenciyi belirleyici bir şekilde bir varianta atar.
    Aynı öğrenci her zaman aynı varianta düşer (deterministic hashing).
    """
    experiment = _EXPERIMENTS.get(experiment_id)
    if not experiment or not experiment.active:
        return "control"

    # Deterministic hash: learner_id + experiment_id → variant index
    hash_input = f"{learner_id}:{experiment_id}"
    hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    variant_index = hash_val % len(experiment.variants)
    variant = experiment.variants[variant_index]

    logger.debug(
        "A/B test | experiment=%s learner=%s variant=%s",
        experiment_id, learner_id, variant,
    )
    return variant


def get_active_experiments() -> list[dict]:
    """Aktif deneylerin listesini döner."""
    return [
        {
            "id": e.id,
            "name": e.name,
            "variants": e.variants,
            "active": e.active,
        }
        for e in _EXPERIMENTS.values()
        if e.active
    ]


def register_experiment(experiment_id: str, name: str, variants: list[str]) -> None:
    """Yeni bir deney kaydeder."""
    _EXPERIMENTS[experiment_id] = Experiment(id=experiment_id, name=name, variants=variants)
