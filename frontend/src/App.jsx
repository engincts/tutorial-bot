import { useEffect, useState } from "react";
import LoginPage from "./components/LoginPage";
import ChatPage from "./components/ChatPage";
import ProfilePage from "./components/ProfilePage";
import styles from "./App.module.css";
import { supabase } from "./supabase";

export default function App() {
  const [auth, setAuth] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [tab, setTab] = useState("chat");

  useEffect(() => {
    // Sayfa yüklendiğinde mevcut oturumu kontrol et
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setAuth({ access_token: session.access_token, learner_id: session.user.id, email: session.user.email });
      }
      setAuthReady(true);
    });

    // Token yenilendiğinde veya oturum değiştiğinde güncelle
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setAuth({ access_token: session.access_token, learner_id: session.user.id, email: session.user.email });
      } else {
        setAuth(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  function handleLogin(data) {
    setAuth(data);
    setTab("chat");
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    setAuth(null);
  }

  if (!authReady) return null;

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
