import { useState, useRef, useEffect, useCallback } from "react";
import { sendChat, resetSession } from "../api";
import MessageBubble from "./MessageBubble";
import MasteryPanel from "./MasteryPanel";
import styles from "./ChatPage.module.css";
import { generateSessionId } from "../utils";

export default function ChatPage({ auth, onLogout }) {
  const { access_token: token, learner_id: learnerId } = auth;

  const [sessionId] = useState(() => generateSessionId());
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      content: "Merhaba! Ben senin kişisel AI öğretmeniniyim. Hangi konuda çalışmak istiyorsun?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mastery, setMastery] = useState({});
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError("");

    const userMsg = { id: Date.now().toString(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await sendChat(token, learnerId, sessionId, text);

      setMessages((prev) => [
        ...prev,
        {
          id: data.session_id + Date.now(),
          role: "assistant",
          content: data.content,
          kc_ids: data.kc_ids,
          model: data.model,
          tokens: data.input_tokens + data.output_tokens,
        },
      ]);

      if (data.mastery_snapshot) {
        setMastery((prev) => ({ ...prev, ...data.mastery_snapshot }));
      }
    } catch (err) {
      setError(err.message);
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
      setInput(text);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, token, learnerId, sessionId]);

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleReset() {
    if (!confirm("Oturumu sıfırlamak istediğine emin misin?")) return;
    try {
      await resetSession(token, learnerId, sessionId);
      setMessages([
        {
          id: "reset",
          role: "assistant",
          content: "Oturum sıfırlandı. Yeni bir konuya başlayabiliriz!",
        },
      ]);
      setMastery({});
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className={styles.layout}>
      {/* ── Header ────────────────────────────────────────────── */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.headerIcon}>🎓</span>
          <span className={styles.headerTitle}>Tutor Bot</span>
        </div>
        <div className={styles.headerRight}>
          <button
            className={styles.iconBtn}
            title="Mastery panelini aç/kapat"
            onClick={() => setSidebarOpen((o) => !o)}
          >
            <ChartIcon />
          </button>
          <button
            className={styles.iconBtn}
            title="Oturumu sıfırla"
            onClick={handleReset}
          >
            <ResetIcon />
          </button>
          <button className={styles.logoutBtn} onClick={onLogout}>
            Çıkış
          </button>
        </div>
      </header>

      {/* ── Body ──────────────────────────────────────────────── */}
      <div className={styles.body}>
        {/* ── Chat ── */}
        <main className={styles.chat}>
          <div className={styles.messages}>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {loading && (
              <div className={styles.typing}>
                <span /><span /><span />
              </div>
            )}

            {error && (
              <div className={styles.errorBanner}>
                {error}
                <button onClick={() => setError("")}>✕</button>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* ── Input ── */}
          <div className={styles.inputWrap}>
            <textarea
              ref={inputRef}
              className={styles.input}
              rows={1}
              placeholder="Bir soru sor veya konu anlat..."
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
              }}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              className={styles.sendBtn}
              onClick={handleSend}
              disabled={loading || !input.trim()}
              title="Gönder (Enter)"
            >
              <SendIcon />
            </button>
          </div>
          <p className={styles.hint}>Enter → gönder &nbsp;·&nbsp; Shift+Enter → yeni satır</p>
        </main>

        {/* ── Sidebar ── */}
        {sidebarOpen && (
          <aside className={styles.sidebar}>
            <MasteryPanel mastery={mastery} />
          </aside>
        )}
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

function ResetIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.63" />
    </svg>
  );
}
