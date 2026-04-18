import styles from "./ConversationSidebar.module.css";
import { deleteConversation } from "../api";

function timeLabel(dateStr) {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return "Az önce";
  if (diff < 3600) return `${Math.floor(diff / 60)}dk önce`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}sa önce`;
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

export default function ConversationSidebar({
  token,
  sessions,
  activeId,
  onSelect,
  onNew,
  onDeleted,
}) {
  async function handleDelete(e, id) {
    e.stopPropagation();
    if (!confirm("Bu sohbeti sil?")) return;
    await deleteConversation(token, id);
    onDeleted(id);
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <span className={styles.heading}>Sohbetler</span>
        <button className={styles.newBtn} onClick={onNew} title="Yeni sohbet">
          <PlusIcon />
        </button>
      </div>

      <div className={styles.list}>
        {sessions.length === 0 && (
          <p className={styles.empty}>Henüz sohbet yok.</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`${styles.item} ${s.id === activeId ? styles.active : ""}`}
            onClick={() => onSelect(s)}
          >
            <div className={styles.itemBody}>
              <span className={styles.title}>{s.title}</span>
              <span className={styles.time}>{timeLabel(s.updated_at)}</span>
            </div>
            <button
              className={styles.deleteBtn}
              onClick={(e) => handleDelete(e, s.id)}
              title="Sil"
            >
              <TrashIcon />
            </button>
          </div>
        ))}
      </div>
    </aside>
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

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}
