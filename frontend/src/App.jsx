import { useState } from "react";
import LoginPage from "./components/LoginPage";
import ChatPage from "./components/ChatPage";

export default function App() {
  const [auth, setAuth] = useState(() => {
    try {
      const raw = localStorage.getItem("tb_auth");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  function handleLogin(data) {
    localStorage.setItem("tb_auth", JSON.stringify(data));
    setAuth(data);
  }

  function handleLogout() {
    localStorage.removeItem("tb_auth");
    setAuth(null);
  }

  if (!auth) return <LoginPage onLogin={handleLogin} />;
  return <ChatPage auth={auth} onLogout={handleLogout} />;
}
