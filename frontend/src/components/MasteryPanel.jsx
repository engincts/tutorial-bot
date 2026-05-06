import styles from "./MasteryPanel.module.css";

const LEVELS = [
  { max: 0.4, label: "Temel", color: "#ef4444" },
  { max: 0.7, label: "Gelişiyor", color: "#f59e0b" },
  { max: 1.0, label: "Uzman", color: "#22c55e" },
];

function getLevel(score) {
  return LEVELS.find((l) => score < l.max) || LEVELS[LEVELS.length - 1];
}

export default function MasteryPanel({ mastery }) {
  const entries = Object.entries(mastery).sort((a, b) => b[1] - a[1]);
  const avg =
    entries.length > 0
      ? entries.reduce((s, [, v]) => s + v, 0) / entries.length
      : null;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>Bilgi Seviyem</h2>
        {avg !== null && (
          <span
            className={styles.avgBadge}
            style={{ background: getLevel(avg).color + "20", color: getLevel(avg).color }}
          >
            Ort. {Math.round(avg * 100)}%
          </span>
        )}
      </div>

      {entries.length === 0 ? (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>📊</span>
          <p>Henüz konu çalışılmadı.</p>
          <p>Bir soru sor, mastery takip edilsin!</p>
        </div>
      ) : (
        <div className={styles.list}>
          {entries.map(([kc, score]) => {
            const level = getLevel(score);
            const pct = Math.round(score * 100);
            return (
              <div key={kc} className={styles.item}>
                <div className={styles.itemHeader}>
                  <span className={styles.kcName}>{kc.replace(/_/g, " ")}</span>
                  <span className={styles.pct} style={{ color: level.color }}>{pct}%</span>
                </div>
                <div className={styles.bar}>
                  <div
                    className={styles.fill}
                    style={{ width: `${pct}%`, background: level.color }}
                  />
                </div>
                <span className={styles.levelLabel} style={{ color: level.color }}>
                  {level.label}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div className={styles.legend}>
        {LEVELS.map((l) => (
          <div key={l.label} className={styles.legendItem}>
            <span className={styles.dot} style={{ background: l.color }} />
            <span>{l.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
