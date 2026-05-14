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
    // Supabase erişilemezse 3 saniyede timeout — login ekranını göster
    const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 3000));
    Promise.race([supabase.auth.getSession(), timeout])
      .then(({ data: { session } }) => {
        if (session) {
          setAuth({
            access_token: session.access_token,
            learner_id: session.user.id,
            email: session.user.email,
          });
        }
      })
      .catch(() => {
        // Hata durumunda auth'u temizle (redirect tetikler)
        setAuth(null);
      })
      .finally(() => {
        setAuthReady(true);
      });

    // Token yenilendiğinde veya oturum değiştiğinde güncelle
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        setAuth({
          access_token: session.access_token,
          learner_id: session.user.id,
          email: session.user.email,
        });
      } else {
        setAuth(null);
      }
    });

    // Kullanıcı sekmeye geri döndüğünde oturumu tazele/kontrol et
    const handleFocus = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) setAuth(null);
      } catch {
        setAuth(null);
      }
    };
    window.addEventListener("focus", handleFocus);

    return () => {
      subscription.unsubscribe();
      window.removeEventListener("focus", handleFocus);
    };
  }, []);

  function handleLogin(data) {
    setAuth(data);
    setTab("chat");
  }

  async function handleLogout() {
    try { await supabase.auth.signOut(); } catch {}
    setAuth(null);
  }

  if (!authReady) {
    return (
      <div className={styles.shell} style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "var(--text-3)", fontSize: 14 }}>Yükleniyor…</div>
      </div>
    );
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
          {tab === "profile" && <ProfilePage auth={auth} />}
        </div>
      </div>
    </div>
  );
}
