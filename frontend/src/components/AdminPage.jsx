import { useEffect, useState } from "react";
import api from "../api";
import styles from "./ProfilePage.module.css"; // Reuse some styles or create new

export default function AdminPage({ auth }) {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [qData, setQData] = useState({
    kc_id: "", question_text: "", options: "A, B, C, D", correct_answer: "", explanation: "", difficulty: "medium"
  });

  useEffect(() => {
    async function load() {
      try {
        const [statsData, logsData] = await Promise.all([
          api.admin.getStats(auth.access_token),
          api.admin.getHallucinationLogs(auth.access_token)
        ]);
        if (statsData.detail || logsData.detail) {
           throw new Error(statsData.detail || logsData.detail);
        }
        setStats(statsData);
        setLogs(Array.isArray(logsData) ? logsData : []);
      } catch (err) {
        console.error("Admin data load failed", err);
        setLogs([]);
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
        <h2 className={styles.sectionTitle}>İçerik Yönetimi</h2>
        <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", marginBottom: "32px" }}>
          {/* Müfredat Yükleme */}
          <div style={{ flex: 1, minWidth: "300px", padding: 16, backgroundColor: "var(--bg-2)", borderRadius: 8, border: "1px solid var(--border)" }}>
            <h3>Döküman & Müfredat Yükle</h3>
            <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 12 }}>Genel bilgi havuzuna (RAG) PDF, Word veya TXT dökümanı ekler.</p>
            <input
              type="file"
              id="admin-doc-upload"
              hidden
              accept=".pdf,.docx,.txt,.md"
              onChange={async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                try {
                  setUploading(true);
                  await api.uploadFile(file);
                  alert("Dosya başarıyla yüklendi ve işlendi!");
                } catch (err) {
                  alert("Hata: " + err.message);
                } finally {
                  setUploading(false);
                  e.target.value = "";
                }
              }}
            />
            <button 
              style={{ padding: "8px 16px", background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}
              onClick={() => document.getElementById("admin-doc-upload").click()}
              disabled={uploading}
            >
              {uploading ? "Yükleniyor..." : "Dosya Seç ve Yükle"}
            </button>
          </div>

          {/* Soru Bankası Yükleme Formu */}
          <div style={{ flex: 1, minWidth: "300px", padding: 16, backgroundColor: "var(--bg-2)", borderRadius: 8, border: "1px solid var(--border)" }}>
            <h3>Soru Bankasına Soru Ekle</h3>
            <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 12 }}>LLM için örnek şablon (few-shot) kazanım sorusu ekler.</p>
            <div style={{ marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, fontWeight: 600 }}>Tekli Ekle</span>
              <div>
                <input type="file" id="json-upload" hidden accept=".json" onChange={async (e) => {
                  const file = e.target.files[0];
                  if (!file) return;
                  try {
                    setUploading(true);
                    const res = await api.quiz.uploadBatch(file);
                    alert(res.message || "Toplu yükleme başarılı!");
                  } catch (err) {
                    alert("Hata: " + err.message);
                  } finally {
                    setUploading(false);
                    e.target.value = "";
                  }
                }} />
                <button type="button" onClick={() => document.getElementById("json-upload").click()} disabled={uploading} style={{ padding: "4px 8px", background: "var(--bg-3)", color: "var(--text-1)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 11 }}>
                  Toplu Yükle (JSON)
                </button>
              </div>
            </div>
            <form onSubmit={async (e) => {
              e.preventDefault();
              try {
                setUploading(true);
                await api.quiz.ingestQuestion({
                  ...qData,
                  options: qData.options.split(",").map(s => s.trim())
                });
                alert("Soru başarıyla eklendi!");
                setQData({ kc_id: "", question_text: "", options: "A, B, C, D", correct_answer: "", explanation: "", difficulty: "medium" });
              } catch (err) {
                alert("Hata: " + err.message);
              } finally {
                setUploading(false);
              }
            }} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <input required placeholder="Konu Başlığı (kc_id) ör: matematik_turev" value={qData.kc_id} onChange={e => setQData({...qData, kc_id: e.target.value})} style={{ padding: 8, borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg-1)", color: "var(--text-1)" }} />
              <textarea required placeholder="Soru Metni" rows={3} value={qData.question_text} onChange={e => setQData({...qData, question_text: e.target.value})} style={{ padding: 8, borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg-1)", color: "var(--text-1)", resize: "vertical" }} />
              <input required placeholder="Şıklar (virgülle ayrılmış)" value={qData.options} onChange={e => setQData({...qData, options: e.target.value})} style={{ padding: 8, borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg-1)", color: "var(--text-1)" }} />
              <input required placeholder="Doğru Cevap (şıkla birebir aynı)" value={qData.correct_answer} onChange={e => setQData({...qData, correct_answer: e.target.value})} style={{ padding: 8, borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg-1)", color: "var(--text-1)" }} />
              <input placeholder="Açıklama (Opsiyonel)" value={qData.explanation} onChange={e => setQData({...qData, explanation: e.target.value})} style={{ padding: 8, borderRadius: 4, border: "1px solid var(--border)", background: "var(--bg-1)", color: "var(--text-1)" }} />
              <button type="submit" disabled={uploading} style={{ padding: "8px 16px", background: "var(--green)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", marginTop: 4 }}>
                {uploading ? "Kaydediliyor..." : "Soruyu Kaydet"}
              </button>
            </form>
          </div>
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
