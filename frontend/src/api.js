import { supabase } from "./supabase";

const BASE = "/api";

// Her API çağrısından önce Supabase'den güncel token alır (otomatik refresh)
async function freshToken() {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session) throw new Error("Oturum sona erdi, lütfen tekrar giriş yapın.");
  return session.access_token;
}

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

// Login doğrudan Supabase JS üzerinden — otomatik token refresh devreye girer
export async function login(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message || "Giriş başarısız");
  return {
    access_token: data.session.access_token,
    learner_id: data.user.id,
    email: data.user.email,
  };
}

// Register backend üzerinden (admin API — e-posta onayı gerekmez)
// Backend'den dönen token'larla Supabase oturumu açılır
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
  const data = await res.json();
  await supabase.auth.setSession({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
  });
  return data;
}

export async function sendChat(_token, _learnerId, sessionId, message) {
  const token = await freshToken();
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Yanıt alınamadı");
  }
  return res.json();
}

export async function getProfile(_token, learnerId) {
  const token = await freshToken();
  const res = await fetch(`${BASE}/profile/${learnerId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}

export async function resetSession(_token, learnerId, sessionId) {
  const token = await freshToken();
  const res = await fetch(`${BASE}/session/reset?session_id=${sessionId}`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Oturum sıfırlanamadı");
  return res.json();
}

export async function listConversations(_token) {
  const token = await freshToken();
  const res = await fetch(`${BASE}/conversations`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getConversationMessages(_token, sessionId) {
  const token = await freshToken();
  const res = await fetch(`${BASE}/conversations/${sessionId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function deleteConversation(_token, sessionId) {
  const token = await freshToken();
  await fetch(`${BASE}/conversations/${sessionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}
