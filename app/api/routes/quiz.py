import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.infrastructure.quiz_store import QuizStore
from app.domain.quiz import QuizSession, QuizQuestion
from app.infrastructure.llm import get_llm_client
from app.services.orchestration.quiz_generator import QuizGenerator
from app.api.dependencies import get_content_retriever, get_memory_updater

router = APIRouter(prefix="/quiz", tags=["quiz"])

class GenerateQuizRequest(BaseModel):
    learner_id: uuid.UUID
    kc_id: str

class GenerateQuizResponse(BaseModel):
    quiz_id: uuid.UUID
    question_id: uuid.UUID
    question_text: str
    options: list[str]

class AnswerQuizRequest(BaseModel):
    learner_id: uuid.UUID
    quiz_id: uuid.UUID
    question_id: uuid.UUID
    answer: str

class AnswerQuizResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str

@router.post("/generate", response_model=GenerateQuizResponse)
async def generate_quiz(
    req: GenerateQuizRequest,
    db: AsyncSession = Depends(get_session)
):
    llm = get_llm_client()
    generator = QuizGenerator(llm)
    retriever = get_content_retriever()
    
    # RAG kullanarak ilgili dokümanları bul
    chunks = await retriever.retrieve(db, query=req.kc_id, kc_filter=[req.kc_id], top_k=3)
    context = retriever.to_prompt_context(chunks)
    
    question = await generator.generate_question(req.kc_id, context)
    if not question:
        raise HTTPException(status_code=500, detail="Soru üretilemedi.")
        
    session_obj = QuizSession(learner_id=req.learner_id, kc_id=req.kc_id)
    question.quiz_id = session_obj.id
    session_obj.questions.append(question)
    
    store = QuizStore()
    await store.create_session(db, session_obj)
    
    return GenerateQuizResponse(
        quiz_id=session_obj.id,
        question_id=question.id,
        question_text=question.question_text,
        options=question.options
    )

@router.post("/answer", response_model=AnswerQuizResponse)
async def answer_quiz(
    req: AnswerQuizRequest,
    db: AsyncSession = Depends(get_session)
):
    store = QuizStore()
    q_orm = await store.get_question(db, req.question_id)
    if not q_orm:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
        
    is_correct = (req.answer.strip().lower() == q_orm.correct_answer.strip().lower())
    await store.save_answer(db, req.quiz_id, req.question_id, req.answer, is_correct)
    
    # Background task ile memory update (KT modeline correctness sinyali gitmesi isteniyor, ama biz LLM kullanıyoruz)
    # LLMMasteryEvaluator doğrudan quiz bilgisinden de beslenebilir veya basitçe score atayabiliriz.
    from app.domain.interaction import Interaction, InteractionType
    interaction = Interaction(
        learner_id=req.learner_id,
        session_id=req.quiz_id,
        interaction_type=InteractionType.QUESTION,
        content_summary=f"Quiz - Soru: {q_orm.question_text[:100]} | Cevap: {req.answer}",
        kc_tags=[(await store.get_session(db, req.quiz_id)).kc_id]
    )
    updater = get_memory_updater()
    updater.fire_and_forget(
        interaction=interaction,
        user_message=req.answer,
        assistant_response=f"Doğru cevap: {q_orm.correct_answer}. {q_orm.explanation}"
    )
    
    return AnswerQuizResponse(
        is_correct=is_correct,
        correct_answer=q_orm.correct_answer,
        explanation=q_orm.explanation or ""
    )

class QuizResultResponse(BaseModel):
    quiz_id: uuid.UUID
    score: float | None
    status: str
    
@router.get("/result/{quiz_id}", response_model=QuizResultResponse)
async def get_quiz_result(quiz_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    store = QuizStore()
    quiz = await store.get_session(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz bulunamadı.")
    return QuizResultResponse(
        quiz_id=quiz.id,
        score=quiz.score,
        status=quiz.status
    )


# ── Multi-turn Quiz (#25) ──────────────────────────────────────────────

class BatchQuizRequest(BaseModel):
    learner_id: uuid.UUID
    kc_id: str
    question_count: int = 5

class BatchQuizResponse(BaseModel):
    quiz_id: uuid.UUID
    questions: list[GenerateQuizResponse]
    total_questions: int

@router.post("/generate-batch", response_model=BatchQuizResponse)
async def generate_batch_quiz(
    req: BatchQuizRequest,
    db: AsyncSession = Depends(get_session)
):
    """Birden fazla soru içeren bir quiz oturumu oluşturur."""
    llm = get_llm_client()
    generator = QuizGenerator(llm)
    retriever = get_content_retriever()

    chunks = await retriever.retrieve(db, query=req.kc_id, kc_filter=[req.kc_id], top_k=5)
    context = retriever.to_prompt_context(chunks)

    session_obj = QuizSession(learner_id=req.learner_id, kc_id=req.kc_id)
    generated_questions = []

    for i in range(min(req.question_count, 10)):
        question = await generator.generate_question(
            req.kc_id,
            f"{context}\n\n(Soru #{i+1} — daha öncekilerden farklı bir soru üret)"
        )
        if question:
            question.quiz_id = session_obj.id
            session_obj.questions.append(question)
            generated_questions.append(
                GenerateQuizResponse(
                    quiz_id=session_obj.id,
                    question_id=question.id,
                    question_text=question.question_text,
                    options=question.options,
                )
            )

    if not generated_questions:
        raise HTTPException(status_code=500, detail="Hiç soru üretilemedi.")

    store = QuizStore()
    await store.create_session(db, session_obj)

    return BatchQuizResponse(
        quiz_id=session_obj.id,
        questions=generated_questions,
        total_questions=len(generated_questions),
    )


# ── Adaptive Difficulty (#26) ──────────────────────────────────────────

class AdaptiveQuizRequest(BaseModel):
    learner_id: uuid.UUID
    kc_id: str

@router.post("/generate-adaptive", response_model=GenerateQuizResponse)
async def generate_adaptive_quiz(
    req: AdaptiveQuizRequest,
    db: AsyncSession = Depends(get_session),
):
    """Mastery seviyesine göre zorluk ayarlayan quiz sorusu üretir."""
    from sqlalchemy import text
    from app.services.orchestration.quiz_generator import QuizGenerator

    # 1. Öğrencinin bu KC'deki mastery seviyesini çek
    result = await db.execute(
        text("SELECT p_mastery FROM mastery_scores WHERE learner_id = :lid AND kc_id = :kc")
        .bindparams(lid=req.learner_id, kc=req.kc_id)
    )
    row = result.first()
    mastery = float(row[0]) if row else 0.3

    # 2. Mastery'ye göre zorluk belirle
    if mastery < 0.3:
        difficulty = "çok kolay (temel kavram sorusu)"
    elif mastery < 0.5:
        difficulty = "kolay (kavramsal anlama sorusu)"
    elif mastery < 0.7:
        difficulty = "orta (uygulama sorusu)"
    elif mastery < 0.9:
        difficulty = "zor (analiz/sentez sorusu)"
    else:
        difficulty = "çok zor (değerlendirme/eleştirel düşünme sorusu)"

    # 3. Zorluk bilgisiyle soru üret
    llm = get_llm_client()
    generator = QuizGenerator(llm)
    retriever = get_content_retriever()

    chunks = await retriever.retrieve(db, query=req.kc_id, kc_filter=[req.kc_id], top_k=3)
    context = retriever.to_prompt_context(chunks)
    context_with_difficulty = f"{context}\n\nZorluk seviyesi: {difficulty}\nÖğrencinin mevcut hakimiyet oranı: %{int(mastery * 100)}"

    question = await generator.generate_question(req.kc_id, context_with_difficulty)
    if not question:
        raise HTTPException(status_code=500, detail="Soru üretilemedi.")

    session_obj = QuizSession(learner_id=req.learner_id, kc_id=req.kc_id)
    question.quiz_id = session_obj.id
    session_obj.questions.append(question)

    store = QuizStore()
    await store.create_session(db, session_obj)

    return GenerateQuizResponse(
        quiz_id=session_obj.id,
        question_id=question.id,
        question_text=question.question_text,
        options=question.options,
    )

