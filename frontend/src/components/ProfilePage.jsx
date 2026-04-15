import { useState, useEffect } from "react";
import { getProfile } from "../api";
import styles from "./ProfilePage.module.css";

const LEVELS = [
  { max: 0.4, label: "Temel", color: "#ef4444" },
  { max: 0.7, label: "Gelişiyor", color: "#f59e0b" },
  { max: 1.01, label: "Uzman", color: "#22c55e" },
];

function getLevel(score) {
  return LEVELS.find((l) => score < l.max) || LEVELS[LEVELS.length - 1];
}

function subjectAvg(kcs) {
  if (!kcs.length) return 0;
  return kcs.reduce((s, kc) => s + kc.p_mastery, 0) / kcs.length;
}

export default function ProfilePage({ auth }) {
  const { access_token: token, learner_id: learnerId, email } = auth;
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    getProfile(token, learnerId)
      .then((data) => {
        if (data) {
          setProfile(data);
          // İlk subject'i açık başlat
          const firstSubject = Object.keys(data.mastery_by_subject || {})[0];
          if (firstSubject) setExpanded({ [firstSubject]: true });
        } else {
          setError("Profil yüklenemedi.");
        }
      })
      .catch(() => setError("Profil yüklenemedi."));
  }, [token, learnerId]);

  function toggleSubject(subject) {
    setExpanded((prev) => ({ ...prev, [subject]: !prev[subject] }));
  }

  const totalKCs = profile
    ? Object.values(profile.mastery_by_subject).flat().length
    : 0;

  const overallAvg =
    profile && totalKCs > 0
      ? Object.values(profile.mastery_by_subject)
          .flat()
          .reduce((s, kc) => s + kc.p_mastery, 0) / totalKCs
      : null;

  return (
    <div className={styles.page}>
      {/* ── Kullanıcı kartı ── */}
      <div className={styles.userCard}>
        <div className={styles.avatar}>
          {email ? email[0].toUpperCase() : "?"}
        </div>
        <div className={styles.userInfo}>
          <div className={styles.userName}>
            {profile?.display_name || "Öğrenci"}
          </div>
          <div className={styles.userEmail}>{email || "—"}</div>
        </div>
        {overallAvg !== null && (
          <div
            className={styles.overallBadge}
            style={{
              background: getLevel(overallAvg).color + "18",
              color: getLevel(overallAvg).color,
            }}
          >
            <span className={styles.overallPct}>
              {Math.round(overallAvg * 100)}%
            </span>
            <span className={styles.overallLabel}>Genel Ortalama</span>
          </div>
        )}
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {!profile && !error && (
        <div className={styles.loading}>Yükleniyor…</div>
      )}

      {/* ── Mastery — ders bazında ── */}
      {profile && (
        <div className={styles.subjects}>
          {Object.keys(profile.mastery_by_subject).length === 0 ? (
            <div className={styles.empty}>
              Henüz konu verisi yok. Sohbet sekmesine geç, bir kaç soru sor — konular burada otomatik gruplanacak.
            </div>
          ) : (
            Object.entries(profile.mastery_by_subject).map(([subject, kcs]) => {
              const avg = subjectAvg(kcs);
              const lvl = getLevel(avg);
              const open = !!expanded[subject];
              return (
                <div key={subject} className={styles.subjectCard}>
                  {/* Ders başlığı */}
                  <button
                    className={styles.subjectHeader}
                    onClick={() => toggleSubject(subject)}
                  >
                    <div className={styles.subjectLeft}>
                      <span className={styles.chevron}>{open ? "▾" : "▸"}</span>
                      <span className={styles.subjectName}>{subject}</span>
                      <span className={styles.kcCount}>{kcs.length} konu</span>
                    </div>
                    <div className={styles.subjectRight}>
                      <div className={styles.subjectBar}>
                        <div
                          className={styles.subjectFill}
                          style={{ width: `${Math.round(avg * 100)}%`, background: lvl.color }}
                        />
                      </div>
                      <span className={styles.subjectPct} style={{ color: lvl.color }}>
                        {Math.round(avg * 100)}%
                      </span>
                    </div>
                  </button>

                  {/* KC listesi */}
                  {open && (
                    <div className={styles.kcList}>
                      {kcs.map((kc) => {
                        const kcLvl = getLevel(kc.p_mastery);
                        const pct = Math.round(kc.p_mastery * 100);
                        return (
                          <div key={kc.kc_id} className={styles.kcItem}>
                            <div className={styles.kcMeta}>
                              <span className={styles.kcLabel}>{kc.label}</span>
                              <div className={styles.kcRight}>
                                <span
                                  className={styles.kcBadge}
                                  style={{
                                    background: kcLvl.color + "18",
                                    color: kcLvl.color,
                                  }}
                                >
                                  {kcLvl.label}
                                </span>
                                <span className={styles.kcPct} style={{ color: kcLvl.color }}>
                                  {pct}%
                                </span>
                              </div>
                            </div>
                            <div className={styles.kcBar}>
                              <div
                                className={styles.kcFill}
                                style={{ width: `${pct}%`, background: kcLvl.color }}
                              />
                            </div>
                            <span className={styles.kcAttempts}>
                              {kc.attempts} etkileşim
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── Legand ── */}
      {profile && totalKCs > 0 && (
        <div className={styles.legend}>
          {LEVELS.map((l) => (
            <div key={l.label} className={styles.legendItem}>
              <span className={styles.dot} style={{ background: l.color }} />
              <span>{l.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
