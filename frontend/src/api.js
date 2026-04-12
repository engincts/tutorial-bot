const BASE = "/api";

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function login(email, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Giriş başarısız");
  }
  return res.json();
}

export async function register(email, password) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Kayıt başarısız");
  }
  return res.json();
}

export async function sendChat(token, _learnerId, sessionId, message) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Yanıt alınamadı");
  }
  return res.json();
}

export async function getProfile(token, learnerId) {
  const res = await fetch(`${BASE}/profile/${learnerId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function resetSession(token, learnerId, sessionId) {
  const res = await fetch(`${BASE}/session/reset`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ learner_id: learnerId, session_id: sessionId }),
  });
  if (!res.ok) throw new Error("Oturum sıfırlanamadı");
  return res.json();
}
