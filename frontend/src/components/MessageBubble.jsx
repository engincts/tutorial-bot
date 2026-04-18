import ReactMarkdown from "react-markdown";
import styles from "./MessageBubble.module.css";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`${styles.row} ${isUser ? styles.userRow : styles.assistantRow}`}>
      {!isUser && (
        <div className={styles.avatar}>🤖</div>
      )}
      <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.assistantBubble}`}>
        {isUser ? (
          <p className={styles.content}>{message.content}</p>
        ) : (
          <div className={styles.markdown}>
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.kc_ids && message.kc_ids.length > 0 && (
          <div className={styles.tags}>
            {message.kc_ids.map((kc) => (
              <span key={kc} className={styles.tag}>{kc.replace(/_/g, " ")}</span>
            ))}
          </div>
        )}

        {message.model && (
          <p className={styles.meta}>
            {message.model.split("/").pop()} · {message.tokens} token
          </p>
        )}
      </div>
      {isUser && (
        <div className={styles.avatar}>👤</div>
      )}
    </div>
  );
}
