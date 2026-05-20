-- ============================================================
-- 001 — Eksik tabloları oluştur
-- Supabase SQL Editor'da çalıştır.
-- ============================================================

-- pgvector extension (zaten aktifse atlar)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── chat_history (learner interactions + embeddings) ─────────
CREATE TABLE IF NOT EXISTS chat_history (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id       UUID NOT NULL,
    session_id       UUID NOT NULL,
    interaction_type VARCHAR(50) NOT NULL,
    content_summary  TEXT NOT NULL,
    embedding        vector(1024),
    kc_tags          TEXT[],
    correctness      BOOLEAN,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_history_learner_id_idx
    ON chat_history (learner_id);

CREATE INDEX IF NOT EXISTS chat_history_embedding_hnsw
    ON chat_history
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── student_errors (misconception log) ───────────────────────
CREATE TABLE IF NOT EXISTS student_errors (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id  UUID NOT NULL,
    kc_id       TEXT NOT NULL,
    description TEXT NOT NULL,
    resolved    BOOLEAN DEFAULT false,
    detected_at TIMESTAMP DEFAULT NOW()
);

-- ── quiz_sessions ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id  UUID NOT NULL,
    kc_id       VARCHAR(255) NOT NULL,
    status      VARCHAR(50) DEFAULT 'active',
    score       FLOAT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── quiz_questions ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_questions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id        UUID NOT NULL,
    question_text  TEXT NOT NULL,
    options        TEXT,
    correct_answer TEXT NOT NULL,
    explanation    TEXT
);

-- ── quiz_answers ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_answers (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id        UUID NOT NULL,
    question_id    UUID NOT NULL,
    learner_answer TEXT NOT NULL,
    is_correct     BOOLEAN NOT NULL,
    answered_at    TIMESTAMPTZ DEFAULT NOW()
);
