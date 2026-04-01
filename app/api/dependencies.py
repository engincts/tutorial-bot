"""
FastAPI dependency injection factory'leri.
Her servis singleton olarak üretilir ve request'lere inject edilir.
"""
from __future__ import annotations

from functools import lru_cache

from app.infrastructure.database import get_session, get_engine
from app.infrastructure.embedder_factory import get_embedder
from app.infrastructure.llm import get_llm_client
from app.infrastructure.pg_vector_store import PgVectorStore
from app.infrastructure.redis_client import SessionCache
from app.services.content_rag.chunker import Chunker
from app.services.content_rag.ingestion_pipeline import IngestionPipeline
from app.services.content_rag.retriever import ContentRetriever
from app.services.knowledge_tracing import build_tracer
from app.services.knowledge_tracing.kc_mapper import KCMapper
from app.services.knowledge_tracing.mastery_estimator import MasteryEstimator
from app.services.learner_memory.interaction_logger import InteractionLogger
from app.services.learner_memory.memory_updater import MemoryUpdater
from app.services.learner_memory.misconception_store import MisconceptionStore
from app.services.learner_memory.profile_retriever import ProfileRetriever
from app.services.orchestration.chat_orchestrator import ChatOrchestrator
from app.services.orchestration.pedagogy_planner import PedagogyPlanner
from app.services.orchestration.prompt_builder import PromptBuilder
from app.services.orchestration.session_manager import SessionManager
from app.settings import get_settings
from sqlalchemy.ext.asyncio import async_sessionmaker


@lru_cache(maxsize=1)
def get_vector_store() -> PgVectorStore:
    return PgVectorStore()


@lru_cache(maxsize=1)
def get_content_retriever() -> ContentRetriever:
    settings = get_settings()
    return ContentRetriever(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        top_k=settings.content_top_k,
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
    return MasteryEstimator(tracer=tracer, kc_mapper=kc_mapper)


@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    return SessionManager(cache=SessionCache())


@lru_cache(maxsize=1)
def get_memory_updater() -> MemoryUpdater:
    from app.infrastructure.database import _session_factory
    embedder = get_embedder()
    vector_store = get_vector_store()
    return MemoryUpdater(
        session_factory=_session_factory,
        interaction_logger=InteractionLogger(embedder=embedder, vector_store=vector_store),
        misconception_store=get_misconception_store(),
        profile_retriever=get_profile_retriever(),
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
        memory_updater=get_memory_updater(),
        session_manager=get_session_manager(),
        pedagogy_planner=PedagogyPlanner(settings=settings),
        prompt_builder=PromptBuilder(),
    )
