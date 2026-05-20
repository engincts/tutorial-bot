import { useState, useEffect } from "react";
import { quiz } from "../api";
import styles from "./QuizPage.module.css";

const LEVEL_COLORS = { low: "#ef4444", mid: "#f59e0b", high: "#22c55e" };

function masteryColor(m) {
  if (m == null) return "var(--text-3)";
  if (m < 0.4) return LEVEL_COLORS.low;
  if (m < 0.7) return LEVEL_COLORS.mid;
  return LEVEL_COLORS.high;
}

// ── Konu seçim ────────────────────────────────────────────────
function SubjectPicker({ subjects, loading, onStart }) {
  const [selected, setSelected] = useState(null);
  const [count, setCount] = useState(10);

  if (loading) return <div className={styles.center}><p>Konular yükleniyor...</p></div>;

  if (!subjects.length) {
    return (
      <div className={styles.center}>
        <p className={styles.empty}>Soru bankası henüz boş.</p>
        <p className={styles.emptySub}>
          ingest_question_bank.py ile TYT PDF'lerini yükleyin.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.picker}>
      <h2 className={styles.pickerTitle}>Quiz Başlat</h2>
      <p className={styles.pickerSub}>Konu seç, soru bankasından test gel.</p>

      <div className={styles.subjectGrid}>
        {subjects.map((s) => (
          <button
            key={s.kc_id}
            className={`${styles.subjectCard} ${selected?.kc_id === s.kc_id ? styles.selected : ""}`}
            onClick={() => setSelected(s)}
          >
            <span className={styles.subjectLabel}>{s.label}</span>
            <span className={styles.subjectCount}>{s.question_count} soru</span>
            {s.mastery != null ? (
              <span
                className={styles.masteryBadge}
                style={{ background: masteryColor(s.mastery) + "22", color: masteryColor(s.mastery) }}
              >
                %{Math.round(s.mastery * 100)} hakimiyet
              </span>
            ) : (
              <span className={styles.newBadge}>Yeni konu</span>
            )}
          </button>
        ))}
      </div>

      <div className={styles.controls}>
        <label className={styles.countLabel}>
          Soru sayısı:
          <select className={styles.countSelect} value={count} onChange={(e) => setCount(Number(e.target.value))}>
            {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button
          className={styles.startBtn}
          disabled={!selected || selected.question_count === 0}
          onClick={() => onStart(selected, count)}
        >
          Başlat
        </button>
      </div>
      {selected?.question_count === 0 && (
        <p style={{ textAlign: "center", fontSize: "0.8rem", color: "var(--text-3)", marginTop: 8 }}>
          Bu konu için soru bankasında henüz soru yok.
        </p>
      )}
    </div>
  );
}

// ── Quiz oyunu ────────────────────────────────────────────────
function QuizGame({ kcId, quizSessionId, questions, onFinish }) {
  const [idx, setIdx] = useState(0);
  const [feedback, setFeedback] = useState(null);
  const [score, setScore] = useState(0);
  const [loading, setLoading] = useState(false);

  const q = questions[idx];
  const total = questions.length;

  async function handleAnswer(opt) {
    if (feedback || loading) return;
    setLoading(true);
    try {
      const res = await quiz.submitBankAnswer(q.question_id, kcId, opt, quizSessionId);
      setFeedback({ ...res, selected: opt });
      if (res.is_correct) setScore((s) => s + 1);
    } catch {
      setFeedback({ is_correct: false, correct_answer: "?", explanation: "Cevap gönderilemedi.", selected: opt });
    } finally {
      setLoading(false);
    }
  }

  function next() {
    if (idx + 1 >= total) {
      onFinish(score + (feedback?.is_correct ? 1 : 0), total);
      return;
    }
    setFeedback(null);
    setIdx((i) => i + 1);
  }

  function optStyle(opt) {
    if (!feedback) return {};
    if (opt === feedback.correct_answer) return { background: "#22c55e22", borderColor: "#22c55e" };
    if (opt === feedback.selected && opt !== feedback.correct_answer) return { background: "#ef444422", borderColor: "#ef4444" };
    return { opacity: 0.5 };
  }

  return (
    <div className={styles.game}>
      <div className={styles.progress}>
        <div className={styles.progressBar}>
          <div className={styles.progressFill} style={{ width: `${(idx / total) * 100}%` }} />
        </div>
        <span className={styles.progressText}>{idx + 1} / {total}</span>
        <span className={styles.scoreText}>✓ {score}</span>
      </div>

      <div className={styles.questionBox}>
        <p className={styles.questionText}>{q.question_text}</p>
      </div>

      <div className={styles.options}>
        {q.options.map((opt, i) => (
          <button
            key={i}
            className={styles.option}
            style={optStyle(opt)}
            disabled={!!feedback || loading}
            onClick={() => handleAnswer(opt)}
          >
            {opt}
          </button>
        ))}
      </div>

      {feedback && (
        <div className={`${styles.feedback} ${feedback.is_correct ? styles.correct : styles.wrong}`}>
          <strong>{feedback.is_correct ? "✓ Doğru!" : "✗ Yanlış"}</strong>
          {!feedback.is_correct && <span> — Doğru cevap: <strong>{feedback.correct_answer}</strong></span>}
          {feedback.explanation && <p className={styles.explanation}>{feedback.explanation}</p>}
          <button className={styles.nextBtn} onClick={next}>
            {idx + 1 >= total ? "Sonuçları Gör" : "Sonraki →"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Sonuç ekranı ──────────────────────────────────────────────
function ResultScreen({ score, total, label, onRetry, onBack }) {
  const pct = Math.round((score / total) * 100);
  const color = pct >= 70 ? LEVEL_COLORS.high : pct >= 40 ? LEVEL_COLORS.mid : LEVEL_COLORS.low;
  return (
    <div className={styles.result}>
      <div className={styles.resultScore} style={{ color }}>%{pct}</div>
      <p className={styles.resultSub}>{score} / {total} doğru — {label}</p>
      <div className={styles.resultActions}>
        <button className={styles.retryBtn} onClick={onRetry}>Tekrar Dene</button>
        <button className={styles.backBtn} onClick={onBack}>Konu Seç</button>
      </div>
    </div>
  );
}

// ── Ana bileşen ───────────────────────────────────────────────
export default function QuizPage({ auth }) {
  const [subjects, setSubjects] = useState([]);
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [loadingQuiz, setLoadingQuiz] = useState(false);
  const [activeQuiz, setActiveQuiz] = useState(null); // { kcId, label, questions }
  const [result, setResult] = useState(null);
  const [lastSubject, setLastSubject] = useState(null);
  const [lastCount, setLastCount] = useState(10);

  useEffect(() => {
    quiz.getSubjects()
      .then(setSubjects)
      .catch(() => setSubjects([]))
      .finally(() => setLoadingSubjects(false));
  }, []);

  async function handleStart(subject, count) {
    setLastSubject(subject);
    setLastCount(count);
    setLoadingQuiz(true);
    try {
      const data = await quiz.getBankQuiz(subject.kc_id, count);
      setActiveQuiz({ kcId: data.kc_id, quizSessionId: data.quiz_session_id, label: subject.label, questions: data.questions });
      setResult(null);
    } catch (err) {
      alert(err.message || "Sorular yüklenemedi.");
    } finally {
      setLoadingQuiz(false);
    }
  }

  function handleFinish(score, total) {
    setResult({ score, total, label: activeQuiz.label });
    setActiveQuiz(null);
  }

  if (loadingQuiz) {
    return (
      <div className={styles.center}>
        <div className={styles.spinner} />
        <p style={{ marginTop: 16, color: "var(--text-2)" }}>Sorular yükleniyor...</p>
      </div>
    );
  }

  if (result) {
    return (
      <ResultScreen
        {...result}
        onRetry={() => { setResult(null); if (lastSubject) handleStart(lastSubject, lastCount); }}
        onBack={() => setResult(null)}
      />
    );
  }

  if (activeQuiz) {
    return (
      <QuizGame
        kcId={activeQuiz.kcId}
        quizSessionId={activeQuiz.quizSessionId}
        questions={activeQuiz.questions}
        onFinish={handleFinish}
      />
    );
  }

  return (
    <SubjectPicker
      subjects={subjects}
      loading={loadingSubjects}
      onStart={handleStart}
    />
  );
}
