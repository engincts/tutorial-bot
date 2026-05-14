import { useEffect, useState } from "react";
import api from "../api";
import styles from "./ProfilePage.module.css"; // Reuse some styles or create new

export default function AdminPage({ auth }) {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [statsData, logsData] = await Promise.all([
          api.admin.getStats(auth.access_token),
          api.admin.getHallucinationLogs(auth.access_token)
        ]);
        setStats(statsData);
        setLogs(logsData);
      } catch (err) {
        console.error("Admin data load failed", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [auth]);

  if (loading) return <div className={styles.loading}>Yükleniyor…</div>;

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>Sistem Yönetimi</h1>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Sistem İstatistikleri</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 16 }}>
          <StatCard label="Toplam Öğrenci" value={stats?.total_learners} />
          <StatCard label="Aktif Oturumlar" value={stats?.active_sessions} />
          <StatCard label="Ort. Bilgi Seviyesi" value={`%${((stats?.avg_mastery || 0) * 100).toFixed(1)}`} />
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Hallucination Denetimi</h2>
        <div className={styles.logList}>
          {logs.length === 0 ? (
            <div style={{ color: "var(--text-3)" }}>Log bulunamadı.</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} style={{ 
                padding: 12, 
                borderBottom: "1px solid var(--border)",
                backgroundColor: log.score > 0.7 ? "rgba(255,0,0,0.05)" : "transparent"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600, color: log.score > 0.7 ? "var(--red)" : "var(--green)" }}>
                    Skor: {log.score.toFixed(3)}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--text-3)" }}>
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
                <div style={{ marginTop: 8, fontSize: 13 }}>
                  <strong>Yanıt:</strong> {log.assistant_response?.substring(0, 150)}...
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div style={{ padding: 16, backgroundColor: "var(--bg-2)", borderRadius: 8, border: "1px solid var(--border)" }}>
      <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
