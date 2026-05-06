import { useState } from "react";
import { login, register } from "../api";
import styles from "./LoginPage.module.css";

export default function LoginPage({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data =
        mode === "login"
          ? await login(email, password)
          : await register(email, password);
      onLogin(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>🎓</span>
          <h1 className={styles.logoText}>Tutor Bot</h1>
          <p className={styles.logoSub}>Kişiselleştirilmiş AI öğrenme asistanı</p>
        </div>

        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${mode === "login" ? styles.active : ""}`}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Giriş Yap
          </button>
          <button
            className={`${styles.tab} ${mode === "register" ? styles.active : ""}`}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Kayıt Ol
          </button>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label className={styles.label}>E-posta</label>
            <input
              className={styles.input}
              type="email"
              placeholder="ornek@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Şifre</label>
            <input
              className={styles.input}
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button className={styles.submit} type="submit" disabled={loading}>
            {loading ? (
              <span className={styles.spinner} />
            ) : mode === "login" ? (
              "Giriş Yap"
            ) : (
              "Hesap Oluştur"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
