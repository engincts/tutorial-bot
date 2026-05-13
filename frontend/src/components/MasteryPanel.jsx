import { useState } from "react";
import styles from "./MasteryPanel.module.css";

const LEVELS = [
  { max: 0.4,  label: "Başlangıç", color: "#F43F5E" },
  { max: 0.7,  label: "Gelişiyor", color: "#F59E0B" },
  { max: 1.01, label: "Uzman",     color: "#10B981" },
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

export default function MasteryPanel({ mastery, onRefresh }) {
  const [collapsed, setCollapsed] = useState({});
  const [refreshing, setRefreshing] = useState(false);

  const allEntries = Object.values(mastery);
  const groups = groupBySubject(mastery);
  const sortedSubjects = Object.entries(groups).sort(
    ([, a], [, b]) => subjectAvg(b) - subjectAvg(a)
  );

  const totalAvg =
    allEntries.length > 0
      ? allEntries.reduce((s, e) => s + e.score, 0) / allEntries.length
      : null;

  const totalLevel = totalAvg !== null ? getLevel(totalAvg) : null;

  function toggleSubject(subject) {
    setCollapsed((prev) => ({ ...prev, [subject]: !prev[subject] }));
  }

  async function handleRefresh() {
    if (!onRefresh || refreshing) return;
    setRefreshing(true);
    try { await onRefresh(); } finally { setRefreshing(false); }
  }

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <span className={styles.titleIcon}>📊</span>
          <h2 className={styles.title}>Bilgi Seviyem</h2>
        </div>
        <div className={styles.headerActions}>
          {totalAvg !== null && (
            <span
              className={styles.avgBadge}
              style={{
                background: totalLevel.color + "18",
                color: totalLevel.color,
                borderColor: totalLevel.color + "40",
              }}
            >
              {Math.round(totalAvg * 100)}%
            </span>
          )}
          {onRefresh && (
            <button
              className={`${styles.refreshBtn} ${refreshing ? styles.spinning : ""}`}
              onClick={handleRefresh}
              title="Yenile"
            >
              ↻
            </button>
          )}
        </div>
      </div>

      {/* Summary bar when data exists */}
      {totalAvg !== null && (
        <div className={styles.overallBar}>
          <div
            className={styles.overallFill}
            style={{
              width: `${Math.round(totalAvg * 100)}%`,
              background: `linear-gradient(90deg, ${totalLevel.color}88, ${totalLevel.color})`,
            }}
          />
        </div>
      )}

      {/* Content */}
      {sortedSubjects.length === 0 ? (
        <div className={styles.empty}>
          <span className={styles.emptyIcon}>🎓</span>
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
                    <span
                      className={styles.groupArrow}
                      style={{ transform: isOpen ? "rotate(90deg)" : "rotate(0deg)" }}
                    >
                      ▶
                    </span>
                    <span className={styles.groupName}>{subject}</span>
                    <span className={styles.groupCount}>{kcs.length}</span>
                  </div>
                  <div className={styles.groupRight}>
                    <div className={styles.groupBar}>
                      <div
                        className={styles.groupFill}
                        style={{
                          width: `${Math.round(avg * 100)}%`,
                          background: avgLevel.color,
                        }}
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
                            <div className={styles.kcRight}>
                              <span className={styles.kcPct} style={{ color: level.color }}>
                                {pct}%
                              </span>
                              <span
                                className={styles.levelDot}
                                style={{ background: level.color }}
                                title={level.label}
                              />
                            </div>
                          </div>
                          <div className={styles.bar}>
                            <div
                              className={styles.fill}
                              style={{ width: `${pct}%`, background: level.color }}
                            />
                          </div>
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

      {/* Legend */}
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
