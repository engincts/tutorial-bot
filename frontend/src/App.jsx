import { useState } from "react";
import LoginPage from "./components/LoginPage";
import ChatPage from "./components/ChatPage";
import ProfilePage from "./components/ProfilePage";
import styles from "./App.module.css";

export default function App() {
  const [auth, setAuth] = useState(() => {
    try {
      const raw = localStorage.getItem("tb_auth");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [tab, setTab] = useState("chat");

  function handleLogin(data) {
    localStorage.setItem("tb_auth", JSON.stringify(data));
    setAuth(data);
    setTab("chat");
  }

  function handleLogout() {
    localStorage.removeItem("tb_auth");
    setAuth(null);
  }

  if (!auth) return <LoginPage onLogin={handleLogin} />;

  return (
    <div className={styles.shell}>
      {/* ── Top nav ── */}
      <header className={styles.nav}>
        <div className={styles.navBrand}>
          <span className={styles.navIcon}>🎓</span>
          <span className={styles.navTitle}>Tutor Bot</span>
        </div>
        <nav className={styles.tabs}>
          <button
            className={`${styles.tab} ${tab === "chat" ? styles.tabActive : ""}`}
            onClick={() => setTab("chat")}
          >
            Sohbet
          </button>
          <button
            className={`${styles.tab} ${tab === "profile" ? styles.tabActive : ""}`}
            onClick={() => setTab("profile")}
          >
            Profilim
          </button>
        </nav>
        <button className={styles.logoutBtn} onClick={handleLogout}>
          Çıkış
        </button>
      </header>

      {/* ── Content ── */}
      <div className={styles.content}>
        <div className={tab === "chat" ? styles.tabPane : styles.tabPaneHidden}>
          <ChatPage auth={auth} />
        </div>
        <div className={tab === "profile" ? styles.tabPane : styles.tabPaneHidden}>
          <ProfilePage auth={auth} />
        </div>
      </div>
    </div>
  );
}
