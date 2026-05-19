import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_session
from app.infrastructure.quiz_store import QuizStore
from app.domain.quiz import QuizSession, QuizQuestion
from app.infrastructure.llm import get_llm_client
from app.services.orchestration.quiz_generator import QuizGenerator
from app.api.dependencies import get_content_retriever, get_memory_updater
from app.api.dependencies_auth import get_current_admin, get_current_learner_id

router = APIRouter(prefix="/quiz", tags=["quiz"])

class IngestQuestionRequest(BaseModel):
    kc_id: str
    question_text: str
    options: list[str]
    correct_answer: str
    explanation: str = ""
    difficulty: str = "medium"

@router.post("/questions", response_model=dict, dependencies=[Depends(get_current_admin)])
async def ingest_question(req: IngestQuestionRequest, db: AsyncSession = Depends(get_session)):
    """Kazanım sorusu (soru bankasına) ekler."""
    from sqlalchemy import text
    qid = uuid.uuid4()
    await db.execute(
        text("""
            INSERT INTO question_bank (id, kc_id, question_text, options, correct_answer, explanation, difficulty)
            VALUES (:id, :kc_id, :question, :options, :correct, :exp, :diff)
        """).bindparams(
            id=qid,
            kc_id=req.kc_id,
            question=req.question_text,
            options=json.dumps(req.options),
            correct=req.correct_answer,
            exp=req.explanation,
            diff=req.difficulty
        )
    )
    return {"status": "success", "question_id": str(qid)}

@router.post("/questions/upload", response_model=dict, dependencies=[Depends(get_current_admin)])
async def upload_questions_batch(file: UploadFile = File(...), db: AsyncSession = Depends(get_session)):
    """Swagger UI üzerinden JSON formatlı kazanım sorularını (liste) topluca sisteme gömer."""
    from sqlalchemy import text
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Lütfen geçerli bir JSON dosyası yükleyin.")
    
    content = await file.read()
    try:
        questions = json.loads(content)
        if not isinstance(questions, list):
            raise ValueError("JSON kök dizini bir liste (array) olmalıdır.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON ayrıştırma hatası: {str(e)}")

    inserted = 0
    for q in questions:
        kc_id = q.get("kc_id")
        question_text = q.get("question_text")
        options = q.get("options", [])
        correct = q.get("correct_answer")
        if not (kc_id and question_text and options and correct):
            continue  # Eksik verili soruyu atla
        
        qid = uuid.uuid4()
        await db.execute(
            text("""
                INSERT INTO question_bank (id, kc_id, question_text, options, correct_answer, explanation, difficulty)
                VALUES (:id, :kc_id, :question, :options, :correct, :exp, :diff)
            """).bindparams(
                id=qid,
                kc_id=kc_id,
                question=question_text,
                options=json.dumps(options, ensure_ascii=False),
                correct=correct,
                exp=q.get("explanation", ""),
                diff=q.get("difficulty", "medium")
            )
        )
        inserted += 1
    
    await db.commit()
    return {"status": "success", "message": f"{inserted} adet soru başarıyla eklendi."}

async def _get_example_question_prompt(db: AsyncSession, kc_id: str) -> str:
    from sqlalchemy import text
    result = await db.execute(text("SELECT question_text, options, correct_answer, explanation FROM question_bank WHERE kc_id = :kc ORDER BY random() LIMIT 1").bindparams(kc=kc_id))
    row = result.first()
    if row:
        opts = row[1] if isinstance(row[1], list) else json.loads(row[1])
        ex = {
            "question": row[0],
            "options": opts,
            "correct_answer": row[2],
            "explanation": row[3]
        }
        return f"\n\n[DİKKAT: Aşağıdaki kazanım sorusunu ÖRNEK (few-shot) al, onun yapısını ve zorluğunu taklit ederek konuyla ilgili YENİ ve FARKLI bir soru üret:]\n{json.dumps(ex, ensure_ascii=False, indent=2)}"
    return ""

@router.get("/topics", response_model=list[str])
async def get_quiz_topics(db: AsyncSession = Depends(get_session)):
    from sqlalchemy import text
    result = await db.execute(text("SELECT DISTINCT unnest(kc_tags) FROM curriculum_chunks"))
    rows = result.fetchall()
    return sorted(list(set(r[0] for r in rows if r[0])))


# ── Soru bankası tabanlı quiz ──────────────────────────────────────────

class SubjectOut(BaseModel):
    kc_id: str
    label: str
    question_count: int
    mastery: float | None = None


class BankQuestionOut(BaseModel):
    question_id: str
    question_text: str
    options: list[str]


class BankQuizOut(BaseModel):
    kc_id: str
    questions: list[BankQuestionOut]


class BankAnswerRequest(BaseModel):
    question_id: uuid.UUID
    kc_id: str
    selected_answer: str


class BankAnswerOut(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str


def _derive_subject(kc_id: str) -> str:
    """
    kc_id'den quiz'de gösterilecek konu grubunu türetir.
    tyt_biyoloji_hucre  → tyt_biyoloji
    coğrafya_türkiye    → coğrafya
    matematik_turev     → matematik_turev (2 parça, kısa yeterli)
    """
    parts = kc_id.split("_")
    if len(parts) >= 2 and parts[0].lower() in ("tyt", "ayt"):
        return "_".join(parts[:2])
    if len(parts) >= 2 and len(parts[0]) > 3:
        return "_".join(parts[:2])
    return parts[0]


@router.get("/subjects", response_model=list[SubjectOut])
async def get_available_subjects(
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    db: AsyncSession = Depends(get_session),
):
    """
    Kullanıcının sohbette çalıştığı konuları mastery_scores'tan dinamik olarak döner.
    kc_id prefix'inden subject türetilir — subject kolonu 'Genel' olsa bile doğru gruplanır.
    Hiç mastery yoksa question_bank'taki konuları fallback olarak gösterir.
    """
    from sqlalchemy import text

    mastery_rows = await db.execute(
        text("""
            SELECT kc_id, p_mastery
            FROM mastery_scores
            WHERE learner_id = :lid
        """).bindparams(lid=learner_id)
    )
    rows = mastery_rows.fetchall()

    if not rows:
        # Yeni kullanıcı: question_bank'taki konuları göster
        bank_rows = await db.execute(
            text("SELECT kc_id, count(*) FROM question_bank GROUP BY kc_id ORDER BY kc_id")
        )
        return [
            SubjectOut(
                kc_id=r[0],
                label=r[0].replace("_", " ").title(),
                question_count=int(r[1]),
                mastery=None,
            )
            for r in bank_rows.fetchall()
        ]

    # kc_id prefix'ine göre grupla
    groups: dict[str, list[float]] = {}
    for kc_id, p_mastery in rows:
        subject = _derive_subject(kc_id)
        groups.setdefault(subject, []).append(float(p_mastery))

    result = []
    for subject, masteries in groups.items():
        count_row = await db.execute(
            text("SELECT count(*) FROM question_bank WHERE kc_id ILIKE :pat")
            .bindparams(pat=f"%{subject}%")
        )
        question_count = int(count_row.scalar() or 0)
        result.append(SubjectOut(
            kc_id=subject,
            label=subject.replace("_", " ").title(),
            question_count=question_count,
            mastery=round(sum(masteries) / len(masteries), 3),
        ))

    # Sorusu olanlar önce, sonra mastery'ye göre sırala
    result.sort(key=lambda x: (x.question_count == 0, -(x.mastery or 0)))
    return result


@router.get("/bank-quiz", response_model=BankQuizOut)
async def get_bank_quiz(
    kc_id: str,
    count: int = 10,
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    db: AsyncSession = Depends(get_session),
):
    """question_bank'tan rastgele soru çeker."""
    from sqlalchemy import text

    rows = await db.execute(
        text("""
            SELECT id, question_text, options
            FROM question_bank
            WHERE kc_id ILIKE :pat
            ORDER BY random()
            LIMIT :cnt
        """).bindparams(pat=f"%{kc_id}%", cnt=min(count, 20))
    )
    questions = []
    for row in rows.fetchall():
        opts = row[2] if isinstance(row[2], list) else json.loads(row[2])
        questions.append(BankQuestionOut(
            question_id=str(row[0]),
            question_text=row[1],
            options=opts,
        ))

    if not questions:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Bu konu için soru bulunamadı.")

    return BankQuizOut(kc_id=kc_id, questions=questions)


@router.post("/bank-answer", response_model=BankAnswerOut)
async def submit_bank_answer(
    req: BankAnswerRequest,
    learner_id: uuid.UUID = Depends(get_current_learner_id),
    db: AsyncSession = Depends(get_session),
):
    """Cevabı kontrol eder, mastery günceller."""
    from sqlalchemy import text

    row = await db.execute(
        text("SELECT correct_answer, explanation FROM question_bank WHERE id = CAST(:id AS UUID)")
        .bindparams(id=str(req.question_id))
    )
    q = row.first()
    if not q:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")

    correct_answer = q[0]
    explanation = q[1] or ""
    is_correct = req.selected_answer.strip() == correct_answer.strip()

    # quiz_answers tablosuna kayıt at
    from app.infrastructure.quiz_store import QuizAnswerORM
    db.add(QuizAnswerORM(
        quiz_id=req.question_id,
        question_id=req.question_id,
        learner_answer=req.selected_answer,
        is_correct=is_correct,
    ))

    # Mastery güncelle (arka planda)
    from app.domain.interaction import Interaction, InteractionType
    from app.api.dependencies import get_memory_updater
    interaction = Interaction(
        learner_id=learner_id,
        session_id=uuid.uuid4(),
        interaction_type=InteractionType.QUESTION,
        content_summary=f"Quiz cevabı — kc: {req.kc_id}",
        kc_tags=[req.kc_id],
    )
    get_memory_updater().fire_and_forget(
        interaction=interaction,
        new_mastery={req.kc_id: 0.85 if is_correct else 0.15},
        subject=req.kc_id.split("_")[0],
    )

    return BankAnswerOut(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=explanation,
    )

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
    
    example_prompt = await _get_example_question_prompt(db, req.kc_id)
    question = await generator.generate_question(req.kc_id, context + example_prompt)
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

    example_prompt = await _get_example_question_prompt(db, req.kc_id)

    for i in range(min(req.question_count, 10)):
        question = await generator.generate_question(
            req.kc_id,
            f"{context}{example_prompt}\n\n(Soru #{i+1} — daha öncekilerden farklı bir soru üret)"
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
    example_prompt = await _get_example_question_prompt(db, req.kc_id)
    context_with_difficulty = f"{context}{example_prompt}\n\nZorluk seviyesi: {difficulty}\nÖğrencinin mevcut hakimiyet oranı: %{int(mastery * 100)}"

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

