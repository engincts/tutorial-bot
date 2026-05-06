import { useState, useRef, useEffect, useCallback } from "react";
import { sendChat, listConversations, getConversationMessages, getProfile } from "../api";
import MessageBubble from "./MessageBubble";
import MasteryPanel from "./MasteryPanel";
import ConversationSidebar from "./ConversationSidebar";
import styles from "./ChatPage.module.css";
import { generateSessionId } from "../utils";

const WELCOME = {
  id: "welcome",
  role: "assistant",
  content: "Merhaba! Ben senin kişisel AI öğretmeniniyim. Hangi konuda çalışmak istiyorsun?",
};

// mastery state yapısı: { kc_id: { score, subject, label } }
function profileToMasteryMap(profile) {
  const map = {};
  for (const [subject, kcs] of Object.entries(profile.mastery_by_subject || {})) {
    for (const kc of kcs) {
      map[kc.kc_id] = { score: kc.p_mastery, subject, label: kc.label };
    }
  }
  return map;
}

export default function ChatPage({ auth }) {
  const { access_token: token, learner_id: learnerId } = auth;

  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(() => generateSessionId());
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mastery, setMastery] = useState({});
  const [masteryOpen, setMasteryOpen] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // İlk yüklemede profil + sohbet listesini getir
  useEffect(() => {
    listConversations(token).then(setSessions);
    getProfile(token, learnerId).then((profile) => {
      if (profile) setMastery(profileToMasteryMap(profile));
    });
  }, [token, learnerId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Var olan bir sohbeti seç
  async function handleSelectSession(session) {
    setCurrentSessionId(session.id);
    setError("");
    setLoading(true);
    const msgs = await getConversationMessages(token, session.id);
    setMessages(
      msgs.length > 0
        ? msgs.map((m) => ({ id: m.id, role: m.role, content: m.content }))
        : [WELCOME]
    );
    setLoading(false);
    inputRef.current?.focus();
  }

  // Yeni sohbet — mastery kullanıcıya ait, sıfırlanmaz
  function handleNewSession() {
    const id = generateSessionId();
    setCurrentSessionId(id);
    setMessages([WELCOME]);
    setError("");
    inputRef.current?.focus();
  }

  // Sohbet sil
  function handleDeleted(id) {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (id === currentSessionId) handleNewSession();
  }

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setError("");

    const userMsg = { id: Date.now().toString(), role: "user", content: text };
    setMessages((prev) => [...prev.filter((m) => m.id !== "welcome"), userMsg]);
    setLoading(true);

    try {
      const data = await sendChat(token, learnerId, currentSessionId, text);

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
        setMastery((prev) => {
          const next = { ...prev };
          const subjects = data.mastery_subjects || {};
          
          for (const [kc_id, score] of Object.entries(data.mastery_snapshot)) {
            const rawSubject = subjects[kc_id] || kc_id.split("_")[0];
            const subject = rawSubject.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
            
            // Eğer kc_id subject ile başlıyorsa label'dan subject'i çıkar
            let labelSlug = kc_id;
            if (kc_id.startsWith(rawSubject + "_")) {
              labelSlug = kc_id.slice(rawSubject.length + 1);
            }
            const label = labelSlug.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

            next[kc_id] = {
              score,
              subject: prev[kc_id]?.subject || subject,
              label: prev[kc_id]?.label || label,
            };
          }
          return next;
        });
      }

      // Oturum listesini güncelle — başa taşı veya ekle
      setSessions((prev) => {
        const existing = prev.find((s) => s.id === currentSessionId);
        const title = text.slice(0, 60);
        const updated = { id: currentSessionId, title, updated_at: new Date().toISOString(), created_at: existing?.created_at || new Date().toISOString() };
        return [updated, ...prev.filter((s) => s.id !== currentSessionId)];
      });
    } catch (err) {
      setError(err.message);
      setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
      setInput(text);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, token, learnerId, currentSessionId]);

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className={styles.layout}>
      {/* ── Sol: Sohbet listesi ── */}
      <ConversationSidebar
        token={token}
        sessions={sessions}
        activeId={currentSessionId}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        onDeleted={handleDeleted}
      />

      {/* ── Orta: Chat alanı ── */}
      <div className={styles.chatArea}>
        {/* Toolbar */}
        <div className={styles.toolbar}>
          <button
            className={`${styles.iconBtn} ${styles.mobileOnly}`}
            title="Yeni sohbet"
            onClick={handleNewSession}
          >
            <PlusIcon />
          </button>
          <span className={styles.sessionTitle}>
            {sessions.find((s) => s.id === currentSessionId)?.title || "Yeni Sohbet"}
          </span>
          <button
            className={styles.iconBtn}
            title="Bilgi seviyesi"
            onClick={() => setMasteryOpen((o) => !o)}
          >
            <ChartIcon />
          </button>
        </div>

        {/* Mesajlar */}
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

        {/* Input */}
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
      </div>

      {/* ── Sağ: Mastery panel ── */}
      {masteryOpen && (
        <aside className={styles.masteryAside}>
          <MasteryPanel mastery={mastery} />
        </aside>
      )}
    </div>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
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
