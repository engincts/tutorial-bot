import { useEffect, useState } from "react";
import { getProfile } from "../api";
import styles from "./ProfilePage.module.css";

const LEVELS = [
  { max: 0.4,  label: "Başlangıç", color: "#F43F5E", bg: "rgba(244,63,94,.08)" },
  { max: 0.7,  label: "Gelişiyor", color: "#F59E0B", bg: "rgba(245,158,11,.08)" },
  { max: 1.01, label: "Uzman",     color: "#10B981", bg: "rgba(16,185,129,.08)" },
];

function getLevel(score) {
  return LEVELS.find((l) => score < l.max) || LEVELS[LEVELS.length - 1];
}

export default function ProfilePage({ auth }) {
  const { access_token: token, learner_id: learnerId, email } = auth;
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openSubjects, setOpenSubjects] = useState({});

  useEffect(() => {
    setLoading(true);
    setError("");
    getProfile(token, learnerId)
      .then((p) => setProfile(p))
      .catch((e) => setError(e.message || "Profil yüklenemedi"))
      .finally(() => setLoading(false));
  }, [token, learnerId]);

  function toggleSubject(subject) {
    setOpenSubjects((prev) => ({ ...prev, [subject]: !prev[subject] }));
  }

  if (loading) return <div className={styles.loading}>Yükleniyor…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (!profile) return <div className={styles.empty}>Profil bulunamadı.</div>;

  const subjects = profile.mastery_by_subject || {};
  const allKcs = Object.values(subjects).flat();
  const totalAvg = allKcs.length > 0
    ? allKcs.reduce((s, kc) => s + kc.p_mastery, 0) / allKcs.length
    : null;
  const totalLevel = totalAvg !== null ? getLevel(totalAvg) : null;

  return (
    <div className={styles.page}>
      {/* ── User card ── */}
      <div className={styles.userCard}>
        <div className={styles.avatar}>
          {email ? email[0].toUpperCase() : "?"}
        </div>
        <div className={styles.userInfo}>
          <div className={styles.userName}>{profile.display_name || "Öğrenci"}</div>
          <div className={styles.userEmail}>{email}</div>
        </div>
        {totalAvg !== null && (
          <div className={styles.overallBadge} style={{ color: totalLevel.color, borderColor: totalLevel.color + "40" }}>
            <span className={styles.overallPct}>{Math.round(totalAvg * 100)}%</span>
            <span className={styles.overallLabel}>{totalLevel.label}</span>
          </div>
        )}
      </div>

      {/* ── Legend ── */}
      <div className={styles.legend}>
        {LEVELS.map((l) => (
          <div key={l.label} className={styles.legendItem}>
            <span className={styles.dot} style={{ background: l.color }} />
            <span>{l.label}</span>
          </div>
        ))}
      </div>

      {/* ── Subjects ── */}
      {Object.keys(subjects).length === 0 ? (
        <div className={styles.empty}>
          Henüz çalışılan konu yok. Sohbet ederek konulardaki bilgi seviyeni takip edebilirsin!
        </div>
      ) : (
        <div className={styles.subjects}>
          {Object.entries(subjects).map(([subject, kcs]) => {
            const avg = kcs.reduce((s, kc) => s + kc.p_mastery, 0) / kcs.length;
            const avgLevel = getLevel(avg);
            const isOpen = openSubjects[subject] !== false; // default open

            return (
              <div key={subject} className={styles.subjectCard}>
                <button className={styles.subjectHeader} onClick={() => toggleSubject(subject)}>
                  <div className={styles.subjectLeft}>
                    <span className={styles.chevron} style={{ transform: isOpen ? "rotate(90deg)" : "rotate(0)" }}>▶</span>
                    <span className={styles.subjectName}>{subject}</span>
                    <span className={styles.kcCount}>{kcs.length} konu</span>
                  </div>
                  <div className={styles.subjectRight}>
                    <div className={styles.subjectBar}>
                      <div className={styles.subjectFill} style={{ width: `${Math.round(avg * 100)}%`, background: avgLevel.color }} />
                    </div>
                    <span className={styles.subjectPct} style={{ color: avgLevel.color }}>
                      {Math.round(avg * 100)}%
                    </span>
                  </div>
                </button>

                {isOpen && (
                  <div className={styles.kcList}>
                    {kcs.map((kc) => {
                      const level = getLevel(kc.p_mastery);
                      const pct = Math.round(kc.p_mastery * 100);
                      return (
                        <div key={kc.kc_id} className={styles.kcItem}>
                          <div className={styles.kcMeta}>
                            <span className={styles.kcLabel}>{kc.label}</span>
                            <div className={styles.kcRight}>
                              <span className={styles.kcBadge} style={{ color: level.color, background: level.bg, borderColor: level.color + "30" }}>
                                {level.label}
                              </span>
                              <span className={styles.kcPct} style={{ color: level.color }}>{pct}%</span>
                            </div>
                          </div>
                          <div className={styles.kcBar}>
                            <div className={styles.kcFill} style={{ width: `${pct}%`, background: level.color }} />
                          </div>
                          {kc.attempts > 0 && (
                            <span className={styles.kcAttempts}>{kc.attempts} etkileşim</span>
                          )}
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
    </div>
  );
}
