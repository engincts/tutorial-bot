import { supabase } from "./supabase";

const BASE = "/api";

async function freshToken() {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session) {
    await supabase.auth.signOut().catch(() => {});
    throw new Error("Oturum sona erdi, lütfen tekrar giriş yapın.");
  }
  return session.access_token;
}

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function login(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message || "Giriş başarısız");

  let role = "student";
  try {
    const res = await fetch(`${BASE}/profile/${data.user.id}`, { headers: { Authorization: `Bearer ${data.session.access_token}` } });
    if (res.ok) {
      const profile = await res.json();
      role = profile.role || "student";
    }
  } catch (e) {}

  return {
    access_token: data.session.access_token,
    learner_id: data.user.id,
    email: data.user.email,
    role: role,
  };
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
  const data = await res.json();
  await supabase.auth.setSession({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
  });

  let role = "student";
  try {
    const pRes = await fetch(`${BASE}/profile/${data.learner_id}`, { headers: { Authorization: `Bearer ${data.access_token}` } });
    if (pRes.ok) {
      const profile = await pRes.json();
      role = profile.role || "student";
    }
  } catch (e) {}

  return { ...data, role };
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

export async function uploadFile(file) {
  const token = await freshToken();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Dosya yüklenemedi");
  }
  return res.json();
}

export const admin = {
  getStats: async () => {
    const token = await freshToken();
    const res = await fetch(`${BASE}/admin/stats`, { headers: { Authorization: `Bearer ${token}` } });
    return res.json();
  },
  getHallucinationLogs: async () => {
    const token = await freshToken();
    const res = await fetch(`${BASE}/admin/hallucination-logs`, { headers: { Authorization: `Bearer ${token}` } });
    return res.json();
  }
};

export const quiz = {
  // Soru bankasından mevcut konular (öğrenci mastery bilgisiyle zenginleştirilmiş)
  getSubjects: async () => {
    const token = await freshToken();
    const res = await fetch(`${BASE}/quiz/subjects`, { headers: authHeaders(token) });
    if (!res.ok) return [];
    return res.json();
  },
  // Soru bankasından rastgele sorular
  getBankQuiz: async (kcId, count = 10) => {
    const token = await freshToken();
    const res = await fetch(
      `${BASE}/quiz/bank-quiz?kc_id=${encodeURIComponent(kcId)}&count=${count}`,
      { headers: authHeaders(token) }
    );
    if (!res.ok) throw new Error("Sorular yüklenemedi.");
    return res.json();
  },
  // Cevap gönder ve doğruluk kontrol et
  submitBankAnswer: async (questionId, kcId, selectedAnswer, quizSessionId = null) => {
    const token = await freshToken();
    const res = await fetch(`${BASE}/quiz/bank-answer`, {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({
        question_id: questionId,
        kc_id: kcId,
        selected_answer: selectedAnswer,
        quiz_session_id: quizSessionId,
      }),
    });
    if (!res.ok) throw new Error("Cevap gönderilemedi.");
    return res.json();
  },
  // Admin: tek soru ekle
  ingestQuestion: async (questionData) => {
    const token = await freshToken();
    const res = await fetch(`${BASE}/quiz/questions`, {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify(questionData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Soru eklenemedi");
    }
    return res.json();
  },
  // Admin: JSON toplu yükle
  uploadBatch: async (file) => {
    const token = await freshToken();
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE}/quiz/questions/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Dosya yüklenemedi");
    }
    return res.json();
  },
};

export const learner = {
  getProfile: getProfile
};

export default { login, register, sendChat, getProfile, resetSession, listConversations, getConversationMessages, deleteConversation, uploadFile, admin, quiz, learner };
