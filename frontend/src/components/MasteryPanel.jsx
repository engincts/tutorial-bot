import { useState } from "react";
import styles from "./MasteryPanel.module.css";

const LEVELS = [
  { max: 0.4, label: "Temel", color: "#ef4444" },
  { max: 0.7, label: "Gelişiyor", color: "#f59e0b" },
  { max: 1.01, label: "Uzman", color: "#22c55e" },
];

function getLevel(score) {
  return LEVELS.find((l) => score < l.max) || LEVELS[LEVELS.length - 1];
}

// mastery: { kc_id: { score, subject, label } }
function groupBySubject(mastery) {
  const groups = {};
  for (const [kc_id, data] of Object.entries(mastery)) {
    const subject = data.subject || "Genel";
    if (!groups[subject]) groups[subject] = [];
    groups[subject].push({ kc_id, ...data });
  }
  // Her grubu score'a göre azalan sırala
  for (const kcs of Object.values(groups)) {
    kcs.sort((a, b) => b.score - a.score);
  }
  return groups;
}

function subjectAvg(kcs) {
  return kcs.reduce((s, kc) => s + kc.score, 0) / kcs.length;
}

export default function MasteryPanel({ mastery }) {
  const [collapsed, setCollapsed] = useState({});
  const allEntries = Object.values(mastery);
  const groups = groupBySubject(mastery);
  const sortedSubjects = Object.entries(groups).sort(
    ([, a], [, b]) => subjectAvg(b) - subjectAvg(a)
  );

  const totalAvg =
    allEntries.length > 0
      ? allEntries.reduce((s, e) => s + e.score, 0) / allEntries.length
      : null;

  function toggleSubject(subject) {
    setCollapsed((prev) => ({ ...prev, [subject]: !prev[subject] }));
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>Bilgi Seviyem</h2>
        {totalAvg !== null && (
          <span
            className={styles.avgBadge}
            style={{ background: getLevel(totalAvg).color + "22", color: getLevel(totalAvg).color }}
          >
            Ort. {Math.round(totalAvg * 100)}%
          </span>
        )}
      </div>

      {sortedSubjects.length === 0 ? (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>📊</span>
          <p>Henüz konu çalışılmadı.</p>
          <p>Bir soru sor, bilgi takip edilsin!</p>
        </div>
      ) : (
        <div className={styles.groups}>
          {sortedSubjects.map(([subject, kcs]) => {
            const avg = subjectAvg(kcs);
            const avgLevel = getLevel(avg);
            const isOpen = !collapsed[subject];
            return (
              <div key={subject} className={styles.group}>
                <button
                  className={styles.groupHeader}
                  onClick={() => toggleSubject(subject)}
                >
                  <div className={styles.groupLeft}>
                    <span className={styles.groupArrow}>{isOpen ? "▾" : "▸"}</span>
                    <span className={styles.groupName}>{subject}</span>
                    <span className={styles.groupCount}>{kcs.length} konu</span>
                  </div>
                  <div className={styles.groupRight}>
                    <div className={styles.groupBar}>
                      <div
                        className={styles.groupFill}
                        style={{ width: `${Math.round(avg * 100)}%`, background: avgLevel.color }}
                      />
                    </div>
                    <span className={styles.groupPct} style={{ color: avgLevel.color }}>
                      {Math.round(avg * 100)}%
                    </span>
                  </div>
                </button>

                {isOpen && (
                  <div className={styles.kcList}>
                    {kcs.map(({ kc_id, score, label }) => {
                      const level = getLevel(score);
                      const pct = Math.round(score * 100);
                      return (
                        <div key={kc_id} className={styles.kcItem}>
                          <div className={styles.kcHeader}>
                            <span className={styles.kcName}>{label}</span>
                            <span className={styles.kcPct} style={{ color: level.color }}>{pct}%</span>
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
