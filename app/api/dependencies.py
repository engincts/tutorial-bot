"""
FastAPI dependency injection factory'leri.
Her servis singleton olarak üretilir ve request'lere inject edilir.
"""
from __future__ import annotations

from functools import lru_cache

from app.infrastructure.database import get_session, get_engine, get_session_factory
from app.infrastructure.embedder_factory import get_embedder
from app.infrastructure.llm import get_llm_client
from app.infrastructure.pg_vector_store import PgVectorStore
from app.infrastructure.redis_client import SessionCache, WorkerQueue
from app.services.content_rag.chunker import Chunker
from app.services.content_rag.ingestion_pipeline import IngestionPipeline
from app.services.content_rag.reranker import Reranker
from app.services.content_rag.retriever import ContentRetriever
from app.services.knowledge_tracing import build_tracer
from app.services.knowledge_tracing.kc_mapper import KCMapper
from app.services.knowledge_tracing.mastery_estimator import MasteryEstimator
from app.services.learner_memory.interaction_logger import InteractionLogger
from app.services.learner_memory.memory_updater import MemoryUpdater
from app.services.learner_memory.misconception_store import MisconceptionStore
from app.services.learner_memory.profile_retriever import ProfileRetriever
from app.infrastructure.chat_store import ChatStore
from app.services.orchestration.chat_orchestrator import ChatOrchestrator
from app.services.orchestration.correctness_evaluator import CorrectnessEvaluator
from app.services.orchestration.misconception_detector import MisconceptionDetector
from app.services.orchestration.pedagogy_planner import PedagogyPlanner
from app.services.orchestration.prompt_builder import PromptBuilder
from app.services.orchestration.session_manager import SessionManager
from app.settings import get_settings
from sqlalchemy.ext.asyncio import async_sessionmaker


@lru_cache(maxsize=1)
def get_chat_store() -> ChatStore:
    return ChatStore()


@lru_cache(maxsize=1)
def get_vector_store() -> PgVectorStore:
    return PgVectorStore()


@lru_cache(maxsize=1)
def get_content_retriever() -> ContentRetriever:
    settings = get_settings()
    reranker = Reranker(llm_client=get_llm_client()) if settings.rerank_enabled else None
    return ContentRetriever(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        top_k=settings.content_top_k,
        reranker=reranker,
    )


@lru_cache(maxsize=1)
def get_ingestion_pipeline() -> IngestionPipeline:
    return IngestionPipeline(
        chunker=Chunker(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
    )


@lru_cache(maxsize=1)
def get_profile_retriever() -> ProfileRetriever:
    return ProfileRetriever()


@lru_cache(maxsize=1)
def get_misconception_store() -> MisconceptionStore:
    return MisconceptionStore()


@lru_cache(maxsize=1)
def get_mastery_estimator() -> MasteryEstimator:
    settings = get_settings()
    tracer = build_tracer(settings.kt_model)
    kc_mapper = KCMapper(llm_client=get_llm_client())
    return MasteryEstimator(tracer=tracer, kc_mapper=kc_mapper, profile_retriever=get_profile_retriever())


@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    return SessionManager(cache=SessionCache())


@lru_cache(maxsize=1)
def get_worker_queue() -> WorkerQueue:
    return WorkerQueue()


@lru_cache(maxsize=1)
def get_correctness_evaluator() -> CorrectnessEvaluator:
    return CorrectnessEvaluator(llm_client=get_llm_client())


@lru_cache(maxsize=1)
def get_misconception_detector() -> MisconceptionDetector:
    return MisconceptionDetector(llm_client=get_llm_client())


@lru_cache(maxsize=1)
def get_llm_mastery_evaluator():
    from app.services.knowledge_tracing.llm_mastery_evaluator import LLMMasteryEvaluator
    return LLMMasteryEvaluator(llm_client=get_llm_client())


@lru_cache(maxsize=1)
def get_memory_updater() -> MemoryUpdater:
    embedder = get_embedder()
    vector_store = get_vector_store()
    return MemoryUpdater(
        session_factory=get_session_factory(),
        interaction_logger=InteractionLogger(embedder=embedder, vector_store=vector_store),
        misconception_store=get_misconception_store(),
        profile_retriever=get_profile_retriever(),
        mastery_evaluator=get_llm_mastery_evaluator(),
    )


@lru_cache(maxsize=1)
def get_chat_orchestrator() -> ChatOrchestrator:
    settings = get_settings()
    return ChatOrchestrator(
        settings=settings,
        llm_client=get_llm_client(),
        content_retriever=get_content_retriever(),
        vector_store=get_vector_store(),
        profile_retriever=get_profile_retriever(),
        misconception_store=get_misconception_store(),
        mastery_estimator=get_mastery_estimator(),
        worker_queue=get_worker_queue(),
        session_manager=get_session_manager(),
        pedagogy_planner=PedagogyPlanner(settings=settings),
        prompt_builder=PromptBuilder(),
        correctness_evaluator=get_correctness_evaluator(),
        misconception_detector=get_misconception_detector(),
    )
