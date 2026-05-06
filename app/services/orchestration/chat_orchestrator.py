"""
Chat Orchestrator — ana iş akışını yönetir.

Akış (her /chat request'inde):
  1. Session yükle
  2. Paralel: Content RAG + Learner Memory RAG
  3. KC'leri çıkar + mastery tahmin et
  4. Pedagoji stratejisi seç
  5. Prompt inşa et
  6. LLM'e gönder
  7. Response'u session'a ekle + kaydet
  8. Arka planda: memory update (KT + embed)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interaction import InteractionType
from app.infrastructure.llm.base import BaseLLMClient, LLMResponse
from app.infrastructure.pg_vector_store import PgVectorStore
from app.infrastructure.redis_client import WorkerQueue
from app.services.content_rag.retriever import ContentRetriever
from app.services.knowledge_tracing.mastery_estimator import MasteryEstimator
from app.services.learner_memory.misconception_store import MisconceptionStore
from app.services.learner_memory.profile_retriever import ProfileRetriever
from app.services.orchestration.correctness_evaluator import CorrectnessEvaluator
from app.services.orchestration.misconception_detector import MisconceptionDetector
from app.services.orchestration.pedagogy_planner import PedagogyPlanner
from app.services.orchestration.prompt_builder import PromptBuilder
from app.services.orchestration.session_manager import SessionManager
from app.settings import Settings


@dataclass
class ChatRequest:
    learner_id: uuid.UUID
    session_id: uuid.UUID
    message: str


@dataclass
class ChatResponse:
    content: str
    session_id: uuid.UUID
    kc_ids: list[str] = field(default_factory=list)
    mastery_snapshot: dict[str, float] = field(default_factory=dict)
    mastery_subjects: dict[str, str] = field(default_factory=dict)
    retrieved_sources: list[dict] = field(default_factory=list)
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class ChatOrchestrator:
    def __init__(
        self,
        settings: Settings,
        llm_client: BaseLLMClient,
        content_retriever: ContentRetriever,
        vector_store: PgVectorStore,
        profile_retriever: ProfileRetriever,
        misconception_store: MisconceptionStore,
        mastery_estimator: MasteryEstimator,
        worker_queue: WorkerQueue,
        session_manager: SessionManager,
        pedagogy_planner: PedagogyPlanner,
        prompt_builder: PromptBuilder,
        correctness_evaluator: CorrectnessEvaluator,
        misconception_detector: MisconceptionDetector,
    ) -> None:
        self._settings = settings
        self._llm = llm_client
        self._content_retriever = content_retriever
        self._vector_store = vector_store
        self._profile_retriever = profile_retriever
        self._misconception_store = misconception_store
        self._mastery_estimator = mastery_estimator
        self._worker_queue = worker_queue
        self._session_manager = session_manager
        self._pedagogy_planner = pedagogy_planner
        self._prompt_builder = prompt_builder
        self._correctness_evaluator = correctness_evaluator
        self._misconception_detector = misconception_detector

    async def chat(
        self,
        request: ChatRequest,
        db_session: AsyncSession,
    ) -> ChatResponse:
        logger.info("chat | learner=%s session=%s", request.learner_id, request.session_id)

        # ── 1. Session + profil ───────────────────────────────────────
        ctx = await self._session_manager.get_or_create(
            session_id=request.session_id,
            learner_id=request.learner_id,
        )
        profile = await self._profile_retriever.get_or_create(
            db_session, request.learner_id
        )

        # ── 2. Retrieval (sıralı — asyncpg aynı bağlantıda eş zamanlı sorguyu desteklemez)
        query_embedding = await self._content_retriever.embed(request.message)
        content_chunks = await self._content_retriever.retrieve(
            db_session,
            query=request.message,
            embedding=query_embedding,
            kc_filter=ctx.active_kc_ids or None,
            top_k=self._settings.content_top_k,
        )
        memory_interactions = await self._vector_store.search_learner_memory(
            db_session,
            learner_id=request.learner_id,
            query_embedding=query_embedding,
            top_k=self._settings.memory_top_k,
        )

        # ── 3. KC extraction + mastery ────────────────────────────────
        course_names = await self._content_retriever.get_all_subjects(db_session)
        kc_ids, mastery_snapshot = await self._mastery_estimator.estimate_for_query(
            learner_id=request.learner_id,
            query=request.message,
            known_kc_ids=ctx.active_kc_ids,
            db_session=db_session,
            course_names=course_names,
        )

        # ── 4. Misconceptions ─────────────────────────────────────────
        misconceptions = await self._misconception_store.get_unresolved(
            db_session,
            learner_id=request.learner_id,
            kc_ids=kc_ids or None,
        )

        # ── 5. Pedagoji stratejisi ────────────────────────────────────
        pedagogy_directive = await self._pedagogy_planner.select_strategy(mastery_snapshot, db_session)

        # ── 6. Prompt inşa et ─────────────────────────────────────────
        messages = await self._prompt_builder.build(
            user_query=request.message,
            profile=profile,
            mastery_snapshot=mastery_snapshot,
            pedagogy_directive=pedagogy_directive,
            content_chunks=content_chunks,
            memory_interactions=memory_interactions,
            misconceptions=misconceptions,
            conversation_history=ctx.to_conversation_history(n=6),
        )

        logger.debug("pedagogy=%s kc_ids=%s", pedagogy_directive, kc_ids)

        # ── 7. LLM çağrısı ────────────────────────────────────────────
        llm_response: LLMResponse = await self._llm.complete(
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        # ── 8. Session güncelle ───────────────────────────────────────
        ctx.add_turn("user", request.message, kc_tags=kc_ids)
        ctx.add_turn("assistant", llm_response.content, kc_tags=kc_ids)
        ctx.active_kc_ids = kc_ids
        for kc_id, kc in mastery_snapshot.components.items():
            ctx.mastery_snapshot.upsert(kc)
        await self._session_manager.save(ctx)

        # ── 9. Doğruluk tespiti + misconception (Mastery worker'da ölçülecek) ──
        correct, detected_misconceptions = await asyncio.gather(
            self._correctness_evaluator.evaluate(
                user_message=request.message,
                assistant_response=llm_response.content,
                kc_ids=kc_ids,
            ),
            self._misconception_detector.detect(
                user_message=request.message,
                assistant_response=llm_response.content,
                kc_ids=kc_ids,
            ),
        )

        if detected_misconceptions:
            logger.debug("misconceptions detected | %s", detected_misconceptions)

        # KC ID'nin ilk parçası = ders (matematik, fizik…) — worker bunu DB'ye yazar
        subject: str | None = None
        if kc_ids:
            from collections import Counter
            first_parts = [k.split("_")[0] for k in kc_ids]
            subject = Counter(first_parts).most_common(1)[0][0]
        if subject is None and content_chunks:
            from collections import Counter
            subject = Counter(c.document_id for c in content_chunks).most_common(1)[0][0]

        # ── 10. Worker queue'ya iş gönder ─────────────────────────────
        await self._worker_queue.push({
            "learner_id": str(request.learner_id),
            "session_id": str(request.session_id),
            "interaction_type": InteractionType.QUESTION.value,
            "content_summary": request.message[:300],
            "kc_tags": kc_ids,
            "subject": subject,
            "misconceptions": [
                {"kc_id": kc_id, "description": desc}
                for kc_id, desc in detected_misconceptions
            ],
            "user_message": request.message,
            "assistant_response": llm_response.content,
            "context_used": "\n".join([c.content[:200] for c in content_chunks])  # Sadece kısa özet
        })

        logger.info(
            "chat done | model=%s in=%d out=%d",
            llm_response.model, llm_response.input_tokens, llm_response.output_tokens,
        )

        merged_mastery = {
            **{k: v.p_mastery for k, v in mastery_snapshot.components.items()}
        }
        mastery_subjects = {k: v.domain for k, v in mastery_snapshot.components.items()}
        retrieved_sources = [
            {"document_id": c.document_id, "chunk_index": c.chunk_index, "content_preview": c.content[:100]}
            for c in content_chunks
        ]

        return ChatResponse(
            content=llm_response.content,
            session_id=request.session_id,
            kc_ids=kc_ids,
            mastery_snapshot=merged_mastery,
            mastery_subjects=mastery_subjects,
            retrieved_sources=retrieved_sources,
            model=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )

    async def chat_stream(
        self,
        request: ChatRequest,
        db_session: AsyncSession,
    ):
        """SSE streaming — önce tüm context'i hazırlar, sonra LLM token'larını akıtır."""
        logger.info("chat_stream | learner=%s session=%s", request.learner_id, request.session_id)

        # ── 1-6: Aynı hazırlık adımları ──
        ctx = await self._session_manager.get_or_create(
            session_id=request.session_id,
            learner_id=request.learner_id,
        )
        profile = await self._profile_retriever.get_or_create(db_session, request.learner_id)

        query_embedding = await self._content_retriever.embed(request.message)
        content_chunks = await self._content_retriever.retrieve(
            db_session, query=request.message, embedding=query_embedding,
            kc_filter=ctx.active_kc_ids or None, top_k=self._settings.content_top_k,
        )
        memory_interactions = await self._vector_store.search_learner_memory(
            db_session, learner_id=request.learner_id,
            query_embedding=query_embedding, top_k=self._settings.memory_top_k,
        )

        course_names = await self._content_retriever.get_all_subjects(db_session)
        kc_ids, mastery_snapshot = await self._mastery_estimator.estimate_for_query(
            learner_id=request.learner_id, query=request.message,
            known_kc_ids=ctx.active_kc_ids, db_session=db_session, course_names=course_names,
        )
        misconceptions = await self._misconception_store.get_unresolved(
            db_session, learner_id=request.learner_id, kc_ids=kc_ids or None,
        )
        pedagogy_directive = await self._pedagogy_planner.select_strategy(mastery_snapshot, db_session)
        messages = await self._prompt_builder.build(
            user_query=request.message, profile=profile, mastery_snapshot=mastery_snapshot,
            pedagogy_directive=pedagogy_directive, content_chunks=content_chunks,
            memory_interactions=memory_interactions, misconceptions=misconceptions,
            conversation_history=ctx.to_conversation_history(n=6),
        )

        # Metadata event
        merged_mastery = {k: v.p_mastery for k, v in mastery_snapshot.components.items()}
        mastery_subjects = {k: v.domain for k, v in mastery_snapshot.components.items()}
        retrieved_sources = [
            {"document_id": c.document_id, "chunk_index": c.chunk_index, "content_preview": c.content[:100]}
            for c in content_chunks
        ]
        yield {
            "type": "metadata",
            "session_id": str(request.session_id),
            "kc_ids": kc_ids,
            "mastery_snapshot": merged_mastery,
            "mastery_subjects": mastery_subjects,
            "retrieved_sources": retrieved_sources,
        }

        # ── 7. LLM streaming ──
        full_content = ""
        async for token in self._llm.complete_stream(messages=messages, temperature=0.7, max_tokens=1024):
            full_content += token
            yield {"type": "token", "content": token}

        # ── 8. Post-stream: session + worker ──
        ctx.add_turn("user", request.message, kc_tags=kc_ids)
        ctx.add_turn("assistant", full_content, kc_tags=kc_ids)
        ctx.active_kc_ids = kc_ids
        for kc_id, kc in mastery_snapshot.components.items():
            ctx.mastery_snapshot.upsert(kc)
        await self._session_manager.save(ctx)

        correct, detected_misconceptions = await asyncio.gather(
            self._correctness_evaluator.evaluate(
                user_message=request.message, assistant_response=full_content, kc_ids=kc_ids,
            ),
            self._misconception_detector.detect(
                user_message=request.message, assistant_response=full_content, kc_ids=kc_ids,
            ),
        )

        subject: str | None = None
        if kc_ids:
            from collections import Counter
            first_parts = [k.split("_")[0] for k in kc_ids]
            subject = Counter(first_parts).most_common(1)[0][0]
        if subject is None and content_chunks:
            from collections import Counter
            subject = Counter(c.document_id for c in content_chunks).most_common(1)[0][0]

        await self._worker_queue.push({
            "learner_id": str(request.learner_id),
            "session_id": str(request.session_id),
            "interaction_type": InteractionType.QUESTION.value,
            "content_summary": request.message[:300],
            "kc_tags": kc_ids,
            "subject": subject,
            "misconceptions": [{"kc_id": kc_id, "description": desc} for kc_id, desc in detected_misconceptions],
            "user_message": request.message,
            "assistant_response": full_content,
            "context_used": "\n".join([c.content[:200] for c in content_chunks]),
        })

        yield {"type": "done", "session_id": str(request.session_id)}

