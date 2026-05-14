import { useState, useEffect } from "react";
import api from "../api";
import styles from "./ChatPage.module.css"; // Reuse chat layout or similar

export default function QuizPage({ auth }) {
  const [kcList, setKcList] = useState([]);
  const [selectedKc, setSelectedKc] = useState("");
  const [quiz, setQuiz] = useState(null);
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    // Profil sayfasından mevcut KC'leri alabiliriz veya sabit bir liste
    async function loadKcs() {
      try {
        const profile = await api.learner.getProfile(auth.learner_id, auth.access_token);
        setKcList(Object.keys(profile.mastery_snapshot || {}));
      } catch (err) {
        console.error("KC list load failed", err);
      }
    }
    loadKcs();
  }, [auth]);

  async function startQuiz() {
    if (!selectedKc) return;
    setLoading(true);
    try {
      const data = await api.quiz.generateBatch(auth.learner_id, selectedKc, 5, auth.access_token);
      setQuiz(data);
      setCurrentQuestionIdx(0);
      setCompleted(false);
      setFeedback(null);
    } catch (err) {
      alert("Quiz başlatılamadı.");
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer(answer) {
    if (feedback) return;
    setLoading(true);
    try {
      const question = quiz.questions[currentQuestionIdx];
      const result = await api.quiz.submitAnswer(
        auth.learner_id,
        quiz.quiz_id,
        question.question_id,
        answer,
        auth.access_token
      );
      setFeedback(result);
    } catch (err) {
      alert("Cevap gönderilemedi.");
    } finally {
      setLoading(false);
    }
  }

  function nextQuestion() {
    setFeedback(null);
    if (currentQuestionIdx + 1 < quiz.questions.length) {
      setCurrentQuestionIdx(idx => idx + 1);
    } else {
      setCompleted(true);
    }
  }

  if (!quiz) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <h2>Adaptif Quiz Başlat</h2>
        <p style={{ color: "var(--text-3)", marginBottom: 24 }}>Bir konu seçin ve kendinizi test edin.</p>
        <select 
          value={selectedKc} 
          onChange={e => setSelectedKc(e.target.value)}
          style={{ padding: 12, borderRadius: 8, marginRight: 8, width: 250 }}
        >
          <option value="">Konu Seçin...</option>
          {kcList.map(kc => <option key={kc} value={kc}>{kc}</option>)}
        </select>
        <button 
          onClick={startQuiz} 
          disabled={!selectedKc || loading}
          style={{ padding: "12px 24px", borderRadius: 8, backgroundColor: "var(--primary)", color: "white" }}
        >
          {loading ? "Hazırlanıyor..." : "Başlat"}
        </button>
      </div>
    );
  }

  if (completed) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <h2>Quiz Tamamlandı!</h2>
        <p style={{ fontSize: 18, margin: "24px 0" }}>Tebrikler, tüm soruları yanıtladınız.</p>
        <button onClick={() => setQuiz(null)} style={{ padding: "12px 24px", borderRadius: 8, backgroundColor: "var(--primary)", color: "white" }}>
          Yeni Quiz
        </button>
      </div>
    );
  }

  const question = quiz.questions[currentQuestionIdx];

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 40 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <span>Soru {currentQuestionIdx + 1} / {quiz.questions.length}</span>
        <span>Konu: {selectedKc}</span>
      </div>

      <div style={{ padding: 32, backgroundColor: "var(--bg-2)", borderRadius: 16, border: "1px solid var(--border)", marginBottom: 24 }}>
        <h3 style={{ marginBottom: 24, lineHeight: 1.5 }}>{question.question_text}</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {question.options.map((opt, i) => (
            <button
              key={i}
              onClick={() => submitAnswer(opt)}
              disabled={!!feedback || loading}
              style={{
                padding: 16,
                textAlign: "left",
                borderRadius: 8,
                border: "1px solid var(--border)",
                backgroundColor: feedback ? (opt === feedback.correct_answer ? "rgba(0,255,0,0.1)" : "transparent") : "var(--bg-1)",
                cursor: feedback ? "default" : "pointer"
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>

      {feedback && (
        <div style={{ 
          padding: 24, 
          borderRadius: 12, 
          backgroundColor: feedback.is_correct ? "rgba(0,255,0,0.05)" : "rgba(255,0,0,0.05)",
          border: `1px solid ${feedback.is_correct ? "var(--green)" : "var(--red)"}`
        }}>
          <h4 style={{ color: feedback.is_correct ? "var(--green)" : "var(--red)", marginBottom: 8 }}>
            {feedback.is_correct ? "✅ Doğru!" : "❌ Yanlış"}
          </h4>
          {!feedback.is_correct && <p><strong>Doğru Cevap:</strong> {feedback.correct_answer}</p>}
          <p style={{ marginTop: 8 }}>{feedback.explanation}</p>
          <button 
            onClick={nextQuestion} 
            style={{ marginTop: 16, padding: "8px 16px", borderRadius: 6, backgroundColor: "var(--primary)", color: "white" }}
          >
            Sonraki Soru
          </button>
        </div>
      )}
    </div>
  );
}
