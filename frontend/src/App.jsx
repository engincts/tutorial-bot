import { useEffect, useState } from "react";
import LoginPage from "./components/LoginPage";
import ChatPage from "./components/ChatPage";
import ProfilePage from "./components/ProfilePage";
import QuizPage from "./components/QuizPage";
import AdminPage from "./components/AdminPage";
import styles from "./App.module.css";
import { supabase } from "./supabase";

export default function App() {
  const [auth, setAuth] = useState(null);
  const isAdmin = auth?.role === "admin" || auth?.email === "admin@tutorbot.com";
  const [authReady, setAuthReady] = useState(false);
  const [tab, setTab] = useState("chat");

  useEffect(() => {
    // onAuthStateChange INITIAL_SESSION eventi tek kaynak — hem ilk yüklemede
    // hem token yenilemede hem de oturum değişiminde tetiklenir.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      if (session) {
        // Auth'u hemen set et (role sonra güncellenir, kullanıcı bekletilmez)
        setAuth({
          access_token: session.access_token,
          learner_id: session.user.id,
          email: session.user.email,
          role: "student",
        });
        setAuthReady(true);
        // Role'ü arka planda çek
        try {
          const res = await fetch(`/api/profile/${session.user.id}`, {
            headers: { Authorization: `Bearer ${session.access_token}` },
          });
          if (res.ok) {
            const profile = await res.json();
            setAuth((prev) => prev ? { ...prev, role: profile.role || "student" } : prev);
          }
        } catch {}
      } else {
        setAuth(null);
        setAuthReady(true);
      }
    });

    // Kullanıcı sekmeye geri döndüğünde oturumun hâlâ geçerli olup olmadığını kontrol et
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
          <button
            className={`${styles.tab} ${tab === "quiz" ? styles.tabActive : ""}`}
            onClick={() => setTab("quiz")}
          >
            Quiz
          </button>
          {isAdmin && (
            <button
              className={`${styles.tab} ${tab === "admin" ? styles.tabActive : ""}`}
              onClick={() => setTab("admin")}
            >
              Yönetim
            </button>
          )}
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
        <div className={tab === "quiz" ? styles.tabPaneScroll : styles.tabPaneHidden}>
          {tab === "quiz" && <QuizPage auth={auth} />}
        </div>
        {isAdmin && (
          <div className={tab === "admin" ? styles.tabPane : styles.tabPaneHidden}>
            {tab === "admin" && <AdminPage auth={auth} />}
          </div>
        )}
      </div>
    </div>
  );
}
