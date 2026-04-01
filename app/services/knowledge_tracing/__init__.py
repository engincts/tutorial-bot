from app.services.knowledge_tracing.akt_model import AKTModel
from app.services.knowledge_tracing.base import BaseKnowledgeTracer
from app.services.knowledge_tracing.dkt_model import DKTModel
from app.services.knowledge_tracing.kc_mapper import KCMapper
from app.services.knowledge_tracing.mastery_estimator import MasteryEstimator
from app.settings import KTModel, get_settings


def build_tracer(kt_model: KTModel | None = None) -> BaseKnowledgeTracer:
    model = kt_model or get_settings().kt_model
    if model == KTModel.AKT:
        return AKTModel(checkpoint_path=get_settings().kt_model_path or None)
    return DKTModel()


__all__ = [
    "AKTModel",
    "BaseKnowledgeTracer",
    "DKTModel",
    "KCMapper",
    "MasteryEstimator",
    "build_tracer",
]