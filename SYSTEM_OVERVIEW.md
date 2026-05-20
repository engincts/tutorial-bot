# Tutor Bot — Sistem Mimarisi ve Detaylı Teknik Döküman

> PowerPoint hazırlık referansı · Tüm bileşenler, algoritmalar, DB tabloları ve akışlar

---

## 1. Sistem Nedir?

**Tutor Bot**, TYT/AYT öğrencilerine yönelik kişiselleştirilmiş bir yapay zeka öğrenme asistanıdır.  
Her öğrencinin bilgi seviyesini matematiksel modelle sürekli ölçer ve buna göre açıklama stratejisini, soru zorluğunu, prompt içeriğini dinamik olarak ayarlar.

### Temel Özellikler

| Özellik | Açıklama |
|---|---|
| Kişiselleştirilmiş sohbet | Her öğrencinin bilgi seviyesine göre farklı pedagoji ve açıklama |
| Bilgi takibi (Knowledge Tracing) | BKT algoritmasıyla her konuda ustalık 0–1 arasında matematiksel olarak ölçülür |
| Adaptif quiz | Kullanıcının çalıştığı konulardan dinamik quiz; doğru/yanlış mastery'yi günceller |
| Yanılgı tespiti | LLM yanlış kavramları tespit eder, kayıt altına alır, sonraki sorularda uyarır |
| Semantik hafıza | Geçmiş etkileşimler vektör DB'de saklanır; benzer sorularda geri çağrılır |
| RAG | Halüsinasyonu azaltmak için LLM kendi bilgisi yerine yüklenen ders içeriklerini kullanır |

---

## 2. Teknoloji Yığını

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│   React + Vite  ·  CSS Modules  ·  Supabase JS SDK  │
└─────────────────────────┬───────────────────────────┘
                          │ HTTP REST
┌─────────────────────────▼───────────────────────────┐
│                   BACKEND (API)                      │
│   FastAPI (Python 3.11)  ·  SQLAlchemy (async)       │
│   Pydantic Settings  ·  Uvicorn                      │
└──────┬──────────────────┬──────────────────┬─────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼──────┐  ┌───────▼────────┐
│    Redis    │  │  PostgreSQL   │  │   Novita AI    │
│ Oturum önb. │  │  (Supabase)   │  │ gpt-oss-120b   │
│ + İş kuyruğu│  │  + pgvector   │  │ + BGE-M3 embed │
└──────┬──────┘  └───────────────┘  └────────────────┘
       │
┌──────▼──────┐
│   WORKER    │
│  (Arka plan │
│   işçisi)   │
└─────────────┘
```

### Docker Servisleri

| Servis | Teknoloji | Port | Görev |
|---|---|---|---|
| `frontend` | Node 20 + React | 3000 | Kullanıcı arayüzü |
| `api` | Python 3.11 + FastAPI | 8005 | REST API |
| `worker` | Python 3.11 | — | Arka plan bellek güncelleme |
| `redis` | Redis 7 | 6379 | Oturum + iş kuyruğu |
| **Supabase** | PostgreSQL + Auth | — | Bulut DB + kimlik doğrulama |

---

## 2.1 Kullanılan Modeller

Tüm model seçimleri `config.json` üzerinden yapılır; `.env` değişkenleri öncelik taşır.

### LLM (Dil Modeli)

| Parametre | Aktif Değer | Alternatifler |
|---|---|---|
| `llm.provider` | `novita` | `openai`, `anthropic` |
| `llm.novita_model` | `openai/gpt-oss-120b` | — |
| `llm.openai_model` | `gpt-4o` | (provider=openai seçilince) |
| `llm.anthropic_model` | `claude-sonnet-4-5` | (provider=anthropic seçilince) |

> LLM; sohbet yanıtı, mastery değerlendirmesi, misconception tespiti, doğruluk değerlendirmesi ve reflection üretimi için kullanılır.

### Embedding Modeli

| Parametre | Aktif Değer | Alternatifler |
|---|---|---|
| `embedder.provider` | `novita` | `bge_m3` (local), `openai` |
| `embedder.novita_model` | `baai/bge-m3` | — |
| `embedder.openai_model` | `text-embedding-3-large` | (provider=openai seçilince) |
| `embedder.model` | `BAAI/bge-m3` | (provider=bge_m3 local seçilince) |
| `embedder.dim` | `1024` | — |

> BGE-M3, hem Content RAG hem Memory RAG için aynı embedding üretir; bir sorguda tek kez çağrılır.

### Knowledge Tracing Modeli

| Parametre | Aktif Değer | Kaynak | Alternatifler |
|---|---|---|---|
| `KT_MODEL` | `bkt` | `.env` (OS env — config.json'u ezer) | `akt`, `dkt` |
| `knowledge_tracing.model_path` | `./checkpoints/akt_assistments.pt` | `config.json` | — |

> `.env` → docker-compose `env_file` → OS env olarak yüklenir → Pydantic öncelik sırası: OS env > config.json > .env dosyası.  
> Soft-BKT update formülü tüm modellerde ortaktır: `p_new = p_old + 0.2 × (llm_score − p_old)`

### Vision Modeli (Soru Bankası Çıkarımı)

| Parametre | Değer | Kullanım |
|---|---|---|
| Model | `qwen/qwen3-vl-235b-a22b-instruct` | Novita AI üzerinden |
| Provider | Novita AI (OpenAI uyumlu API) | — |
| Script | `scripts/ingest_question_bank.py` | — |

> Sadece veri hazırlama aşamasında kullanılır (PDF → soru bankası). Runtime'da çağrılmaz.  
> PDF sayfaları JPEG'e dönüştürülür → base64 → vision model → JSON soru listesi çıkarılır.

---

## 3. Veritabanı Şeması (Supabase PostgreSQL)

### 3.1 `student_profiles`
Öğrenci kimlik ve tercih bilgileri.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Supabase Auth user_id ile aynı |
| `display_name` | TEXT | Görünen ad |
| `preferred_language` | TEXT | "tr" / "en" |
| `preferences` | JSONB | Açıklama stili, öğrenme hızı, son reflection |
| `role` | TEXT | "student" / "admin" |
| `created_at` | TIMESTAMP | Kayıt tarihi |

---

### 3.2 `mastery_scores` ← Sistemin Kalbi
**Her öğrencinin her konu için anlık bilgi seviyesi.**  
Tüm kişiselleştirme, pedagoji seçimi ve quiz adaptasyonu bu tablodan beslenir.

| Kolon | Tür | Açıklama |
|---|---|---|
| `learner_id` | UUID PK | Öğrenci |
| `kc_id` | TEXT PK | Konu kodu: `felsefe_varoluş`, `tyt_biyoloji_hücre` |
| `p_mastery` | FLOAT | Bilgi seviyesi 0.0 → 1.0 |
| `attempts` | INT | Toplam etkileşim sayısı |
| `last_interaction` | TIMESTAMP | Son güncelleme |
| `subject` | TEXT | Ders adı: "matematik", "coğrafya" |

> **`kc_id` format:** `{ders}_{konu}_{kavram}` — örn: `tyt_matematik_turev_zincir_kurali`

---

### 3.3 `question_bank`
Admin tarafından yüklenen TYT/AYT soruları.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Soru ID |
| `kc_id` | TEXT | Konuya ait: `tyt_biyoloji` |
| `question_text` | TEXT | Soru metni |
| `options` | JSONB | `["A) ...", "B) ...", "C) ..."]` |
| `correct_answer` | TEXT | Doğru şık tam metni |
| `explanation` | TEXT | Çözüm açıklaması |
| `difficulty` | TEXT | "easy" / "medium" / "hard" |

---

### 3.4 `curriculum_chunks`
RAG için PDF kaynaklı bölünmüş ders içerikleri.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Parça ID |
| `document_id` | TEXT | Kaynak belge: "tyt_biyoloji" |
| `content` | TEXT | Ham metin |
| `embedding` | VECTOR(1024) | BGE-M3 vektörü — cosine similarity araması için |
| `kc_tags` | TEXT[] | İlgili konu etiketleri |
| `chunk_index` | INT | Belge içindeki sıra |

---

### 3.5 `chat_history`
Tüm etkileşim geçmişi — semantik hafıza (Memory RAG) için vektör olarak saklanır.  
Worker her chat yanıtından sonra buraya yazar; bir sonraki requestte cosine similarity ile top-3 okunur.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Etkileşim ID |
| `learner_id` | UUID | Öğrenci (WHERE filtresi — başkasının hafızası karışmaz) |
| `session_id` | UUID | Oturum |
| `interaction_type` | TEXT | "question" / "misconception" / "success" / "struggle" / "reflection" |
| `content_summary` | TEXT | Özet metin — `"S: {soru[:500]}\nY: {yanıt[:1500]}"` formatında (max ~2000 karakter) |
| `embedding` | VECTOR(1024) | BGE-M3 vektörü — cosine similarity araması için |
| `kc_tags` | TEXT[] | İlgili konu kodları |
| `correctness` | BOOL | Doğru/Yanlış (quiz için) |
| `created_at` | TIMESTAMPTZ | Zaman |

> **Memory RAG kaynağı:** `config.json → retrieval.memory_top_k: 3`  
> Her requestte `search_learner_memory(top_k=3)` → `chat_history WHERE learner_id=:id ORDER BY embedding <=> query LIMIT 3`

---

### 3.6 `student_errors`
LLM tarafından tespit edilen yanılgılar.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | — |
| `learner_id` | UUID | Öğrenci |
| `kc_id` | TEXT | Hangi konuda yanılgı |
| `description` | TEXT | Yanılgı açıklaması |
| `resolved` | BOOL | Giderildi mi? |
| `detected_at` | TIMESTAMP | Tespit tarihi |

---

### 3.7 `quiz_sessions`
Her quiz oturumu kaydı. Hem soru bankası quizi (`GET /quiz/bank-quiz`) hem LLM adaptif quiz (`POST /quiz/generate-adaptive`) tarafından oluşturulur.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Oturum |
| `learner_id` | UUID | Öğrenci |
| `kc_id` | VARCHAR(255) | Konu kodu |
| `score` | FLOAT | Kümülatif puan (% doğru) |
| `status` | TEXT | "active" / "in_progress" / "completed" |
| `created_at` | TIMESTAMPTZ | Başlangıç zamanı |

---

### 3.8 `quiz_questions`
LLM adaptif quiz ile üretilen sorular. Soru bankasından gelen statik sorular buraya değil `question_bank`'a gider.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Soru ID |
| `quiz_id` | UUID | Bağlı quiz oturumu |
| `question_text` | TEXT | Soru metni |
| `options` | TEXT (JSON) | `["A) ...", "B) ..."]` |
| `correct_answer` | TEXT | Doğru şık |
| `explanation` | TEXT | Açıklama |

---

### 3.9 `quiz_answers`
Öğrencinin quiz cevapları. Hem banka hem LLM quiz cevaplarını saklar.

| Kolon | Tür | Açıklama |
|---|---|---|
| `id` | UUID PK | Cevap ID |
| `quiz_id` | UUID | Bağlı quiz oturumu |
| `question_id` | UUID | Sorunun ID'si |
| `learner_answer` | TEXT | Öğrencinin seçtiği şık |
| `is_correct` | BOOL | Doğru mu? |
| `answered_at` | TIMESTAMPTZ | Cevap zamanı |

---

## 4. Kimlik Doğrulama Akışı

```
Kullanıcı          Frontend            Supabase Auth        Backend API
    │                  │                     │                   │
    │── e-posta + ─────►                     │                   │
    │   şifre          │── signInWithPassword►                   │
    │                  │◄──── JWT access_token ──                │
    │                  │── GET /api/profile/{id} ───────────────►│
    │                  │                     │    JWT'yi doğrula │
    │                  │                     │ (SUPABASE_JWT_SECRET)
    │                  │◄──── {role: "student"} ────────────────│
    │◄── Ana sayfa ────│                     │                   │
```

**Oturum yönetimi:**
- Supabase JWT her API isteğinde `Authorization: Bearer <token>` ile gönderilir
- Token süresi dolunca Supabase SDK otomatik yeniler (`onAuthStateChange` eventi)
- `onAuthStateChange` → `INITIAL_SESSION` eventi → tek kaynak of truth, race condition yok
- Sekme odaklanınca `getSession()` ile geçerlilik kontrol edilir

---

## 5. Ana Sohbet Akışı

```
POST /api/chat  {"message": "Türev nedir?", "session_id": "..."}
```

```
[1] OTURUM YÜKLE (Redis, TTL: 1 saat)
    SessionContext: konuşma geçmişi, aktif kc_id'ler, mastery önbelleği

[2] PARALEL HAZIRLIK ──────────────────────────────────────────────────
    ┌─ Content RAG     → pgvector'da cosine similarity, top-5 içerik parçası
    ├─ Memory RAG      → pgvector'da öğrencinin benzer geçmiş etkileşimleri, top-3
    └─ KC Mapper (LLM) → "türev nedir?" → ["matematik_turev_tanim"]

[3] BİLGİ SEVİYESİ TAHMİNİ
    mastery_scores'dan kc_id → p_mastery değeri
    BKT modeline ver → güncel tahmin

[4] YANILGI KONTROLÜ
    student_errors → çözülmemiş yanılgıları yükle

[5] PEDAGOJİ STRATEJİSİ (mastery'ye göre)
    p_mastery < 0.4  → reinforcement.md  (Temel kavramlar)
    p_mastery 0.4–0.7 → practice.md     (Uygulama)
    p_mastery > 0.7  → challenge.md     (Analiz/Sentez)

[6] PROMPT İNŞASI (8 Katman)
    1. system_base.md     — Sokratik yöntem, temel kurallar
    2. Pedagoji direktifi  — Seçilen strateji dosyası
    3. Öğrenci profili     — Ad, tercih ettiği açıklama stili
    4. Mastery snapshot    — "Türev: %72  ███████░░░"
    5. Aktif yanılgılar    — "Zincir kuralını çarpmayı unutuyor"
    6. Memory RAG          — Benzer geçmiş 3 etkileşim
    7. Content RAG         — İlgili ders içeriği (PDF parçaları)
    8. Konuşma geçmişi     — Son 6 mesaj

[7] LLM ÇAĞRISI (Novita → deepseek-v3.2)
    Yanıt üretilir

[8] YANIT KULLANICIYA DÖNER (anlık, worker beklenmez)

[9] OTURUM GÜNCELLE (Redis)
    Yeni mesaj geçmişe eklenir, aktif kc_id'ler güncellenir

[10] WORKER KUYRUĞUNA AT (Redis → fire-and-forget)
     Mastery güncelleme, embedding, yanılgı kaydı arka planda
```

---

## 6. Arka Plan Worker Akışı

`worker` servisi Redis kuyruğunu `BRPOP` ile sürekli dinler. Her chat'ten sonra tetiklenir.

```
Redis'ten iş al
      │
      ▼
[a] Etkileşimi embed et
    content_summary → BGE-M3 → 1024-boyutlu vektör
    chat_history tablosuna yaz

[b] Yanılgıları kaydet
    student_errors tablosuna INSERT

[c] Mastery değerlendir (LLM)
    "Bu konuşmadan öğrenci konuya ne kadar hakim?" → 0.0–1.0
    Her kc_id için ayrı skor döner

[d] BKT soft güncelleme
    p_new = p_old + 0.2 × (llm_score − p_old)
    mastery_scores UPSERT

[e] Reflection (≥10 etkileşimde bir)
    Öğrencinin genel öğrenme özeti LLM ile üretilir
    student_profiles.preferences.last_reflection alanına kaydedilir

[f] Halüsinasyon kontrolü
    Yanıt, kaynak içerikle tutarlı mı? → admin loglarına yazar

session.commit() → tüm değişiklikler kalıcı

Hata yönetimi: 3 deneme, bekleme 2s → 4s → 8s
```

---

## 7. Puanlama ve Bilgi Takibi Algoritması

### 7.0 Genel Akış — İki Farklı Yol

Sistemde mastery güncellemesi **sohbet** ve **quiz** olmak üzere iki farklı yoldan tetiklenir:

```
┌──────────────────────────────────────────────────────────────────────┐
│ YOL A: SOHBET (chat)                                                 │
│                                                                      │
│  Kullanıcı mesajı                                                    │
│       │                                                              │
│       ▼                                                              │
│  LLM yanıt üretir                                                    │
│       │                                                              │
│       ▼  [paralel]                                                   │
│  CorrectnessEvaluator ─── LLM sınıflandırır ──► True / False / None │
│       │                                                              │
│       ├─ True/False → BKT binary update → new_mastery               │
│       └─ None       → new_mastery = None (LLM değerlendiremiyor)    │
│       │                                                              │
│       ▼                                                              │
│  Worker kuyruğuna gönder (new_mastery ile birlikte)                 │
│       │                                                              │
│       ▼  [arka planda]                                               │
│  new_mastery varsa: doğrudan kullan                                  │
│  new_mastery yoksa: LLMMasteryEvaluator → {kc_id: 0.0–1.0}         │
│       │                                                              │
│       ▼                                                              │
│  Soft-BKT formülü → kc_mastery tablosuna UPSERT                     │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ YOL B: QUIZ (soru bankası)                                           │
│                                                                      │
│  Öğrenci şık seçer                                                   │
│       │                                                              │
│       ▼                                                              │
│  selected_answer == correct_answer → is_correct: bool               │
│       │                                                              │
│       ▼                                                              │
│  BKT binary update → new_mastery                                     │
│       │                                                              │
│       ▼                                                              │
│  Worker → Soft-BKT formülü → kc_mastery UPSERT                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

### 7.1 BKT — Bayesian Knowledge Tracing (Aktif Model)

> **Aktif model:** `bkt` (`.env → KT_MODEL=bkt`, OS env olarak yükleniyor)

Her konu (KC) için bağımsız probabilistik bir Hidden Markov Model çalıştırır.

#### BKT Parametreleri

| Parametre | Simge | Değer | Anlamı |
|---|---|---|---|
| Başlangıç bilgisi | P(L₀) | 0.10 | Yeni konu için prior — %10 biliyor olasılığı |
| Öğrenme | P(T) | 0.15 | Her etkileşimde öğrenme olasılığı |
| Kayma (Slip) | P(S) | 0.10 | Biliyor ama yanlış yapma olasılığı |
| Tahmin (Guess) | P(G) | 0.20 | Bilmiyor ama doğru yapma olasılığı |
| Unutma | P(F) | 0.02 | Yanlış sonrası hafif düşüş oranı |
| Alt sınır | — | 0.01 | Mastery asla 0 olmaz |
| Üst sınır | — | 0.99 | Mastery asla 1 olmaz |

#### Binary Güncelleme (Quiz — Kesin Doğru/Yanlış)

```
Adım 1: Bayes Posterior — gözleme göre "gerçekten biliyor mu?" güncelle

  Doğru cevap:
    P(L | ✓) = P(L) × (1 − P(S))
               ─────────────────────────────────────
               P(L)×(1−P(S))  +  (1−P(L))×P(G)

  Yanlış cevap:
    P(L | ✗) = P(L) × P(S)
               ─────────────────────────────────────
               P(L)×P(S)  +  (1−P(L))×(1−P(G))

Adım 2: Öğrenme Geçişi — bir sonraki adım için ön tahmin

  P(L_yeni) = P(L | gözlem)  +  (1 − P(L | gözlem)) × P(T)

Adım 3: Yanlış ise unutma uygula

  P(L_yeni) = P(L_yeni) × (1 − P(F))

Adım 4: Clamp → [0.01, 0.99]

Sayısal örnek (p_old=0.30, doğru cevap):
  posterior = 0.30×0.90 / (0.30×0.90 + 0.70×0.20) = 0.27 / 0.41 = 0.659
  p_new     = 0.659 + (1 − 0.659) × 0.15             = 0.659 + 0.051 = 0.710
```

#### Soft Güncelleme (Sohbet — LLM Güven Skoru)

Sohbet ortamında kesin doğru/yanlış yerine `confidence ∈ [0.0, 1.0]` kullanılır:

```
P(obs|L)   = confidence × (1−P(S))  +  (1−confidence) × P(S)
P(obs|¬L)  = confidence × P(G)      +  (1−confidence) × (1−P(G))

posterior = P(obs|L) × P(L)  /  [P(obs|L)×P(L) + P(obs|¬L)×(1−P(L))]

effective_learn = P(T) × confidence
P(L_yeni) = posterior + (1 − posterior) × effective_learn

confidence < 0.3 → P(L_yeni) = P(L_yeni) × (1 − P(F))  [hafif unutma]
```

---

### 7.2 LLMMasteryEvaluator — Sohbetten Skor Üretme

BKT'nin `correct: bool` bilgisine ihtiyacı var. Sohbette bu her zaman bilinmez.  
`LLMMasteryEvaluator`, öğrenci mesajı + eğitmen yanıtını okuyarak her KC için 0.0–1.0 arası skor üretir.

```
Giriş:
  user_message:       "Yani türev fonksiyonun eğimini mi veriyor?"
  assistant_response: "Evet, türev f'(x) anlık değişim hızıdır..."
  kc_ids:             ["matematik_turev_tanim", "matematik_turev_yorum"]
  current_mastery:    {"matematik_turev_tanim": 0.55, ...}

LLM'e gönderilen prompt (temperature=0, max_tokens=100):
  "Öğrencinin bu konulardaki bilgi seviyesini 0.0–1.0 ile puanla.
   SADECE JSON döndür: {kc_id: skor}"

LLM çıktısı:
  {"matematik_turev_tanim": 0.75, "matematik_turev_yorum": 0.60}
```

---

### 7.3 Soft-BKT Persist Formülü (Worker)

BKT skoru veya LLM skoru ne olursa olsun, `kc_mastery` tablosuna yazılmadan önce bir son yumuşatma adımı uygulanır:

```
learning_rate = 0.20

p_new = p_old + learning_rate × (score − p_old)
p_new = clamp(p_new, 0.01, 0.99)

Örnekler:
  p_old=0.30, score=0.75 → p_new = 0.30 + 0.20×(0.75−0.30) = 0.39
  p_old=0.55, score=0.75 → p_new = 0.55 + 0.20×(0.75−0.55) = 0.59
  p_old=0.80, score=0.20 → p_new = 0.80 + 0.20×(0.20−0.80) = 0.68
```

> Ani sıçramayı engeller. Tek bir doğru cevap mastery'yi 0.3→0.99 yapmaz; kademeli ilerler.

---

### 7.4 AKT — Attentive Knowledge Tracing (Alternatif)

> config.json'da `akt` seçildiğinde aktif olur, `.env`'deki `KT_MODEL=bkt` bunu ezer.

BKT'den farkı: yakın zamanlı etkileşimlere daha fazla ağırlık verir.

```
decay_factor = 0.94

Ağırlıklar (en yeniden eskiye):
  son etkileşim → 1.0
  2. etkileşim  → 0.94
  3. etkileşim  → 0.94² = 0.88
  N. etkileşim  → 0.94^(N−1)

Güven ölçeği (denemeler arttıkça daha güvenilir):
  confidence = 1 − e^(−attempts / 12.0)
  attempts=1  → 0.08   attempts=12 → 0.63   attempts=24 → 0.86
```

---

### 7.5 Mastery Seviyeleri ve Pedagoji Eşikleri

| p_mastery | Seviye | UI Rengi | Pedagoji Modu |
|---|---|---|---|
| 0.00 – 0.40 | Başlangıç | Kırmızı | Reinforcement — temel kavramları pekiştir |
| 0.40 – 0.70 | Gelişiyor | Sarı | Practice — alıştırma ve uygulama |
| 0.70 – 1.00 | Uzman | Yeşil | Challenge — zorlu sorular ve derinleştirme |

---

## 8. KC Mapper — Konu Çıkarımı

Her kullanıcı mesajından hangi konuların sorulduğunu tespit eden bileşen.  
Çıkardığı KC ID'ler sistemin geri kalanı için merkezi bir anahtar görevi görür.

### 8.1 KC Kimliği Nedir?

```
tyt_biyoloji_hucre_bolunmesi
 │       │         │
 │       │         └── Kavram (opsiyonel, alt çizgiyle ayrılır)
 │       └──────────── Konu
 └──────────────────── Ders önek (tyt / ayt / matematik / fizik / ...)

Kurallar:
  - Küçük harf, Türkçe karakter yok (ü→u, ş→s, ğ→g, ç→c, ı→i, ö→o)
  - Kelimeler arası: _ (alt çizgi)
  - Maksimum 4 KC ID üretilir (max_kc_per_query=4)
```

### 8.2 LLM ile Çıkarım (Ana Yol)

```
Kullanıcı: "Türev zincir kuralı nasıl uygulanır?"
                    │
                    ▼
    DB'den tüm ders adları çekilir → course_names
    ["matematik", "fizik", "biyoloji", "turkce", ...]
                    │
                    ▼
    LLM'e gönderilir (temperature=0.1, max_tokens=1000):
      System: "Mesajdaki akademik konuyu JSON array olarak döndür.
               Format: {ders}_{konu}_{kavram}
               Sistemde yüklü dersler: matematik, fizik, ...
               Sadece JSON array, başka hiçbir şey yazma."
      User:   "Metin: Türev zincir kuralı nasıl uygulanır?"
                    │
                    ▼
    LLM döndürür (raw JSON):
      ["matematik_turev_zincir_kurali"]
                    │
                    ▼
    Temizleme: [^a-z0-9_] → "_"  (güvenli karakter seti)
    Sınırlama: ilk 4 eleman alınır
```

### 8.3 Keyword Fallback (LLM Boş Yanıt Verirse)

LLM boş yanıt döndürürse veya erişilemezse, sabit keyword haritasına bakılır:

| Konu | Anahtar Kelimeler |
|---|---|
| `tyt_matematik` | matematik, sayı, cebir, geometri, denklem, fonksiyon |
| `tyt_fizik` | fizik, kuvvet, hareket, enerji, elektrik, newton |
| `tyt_kimya` | kimya, atom, element, asit, baz, mol |
| `tyt_biyoloji` | biyoloji, hücre, canlı, solunum, genetik, evrim |
| `tyt_turkce` | türkçe, dilbilgisi, paragraf, sözcük, yazım |
| `tyt_tarih` | tarih, osmanlı, atatürk, inkılap, cumhuriyet |
| `tyt_cografya` | coğrafya, iklim, harita, nüfus, kıta |
| `tyt_felsefe` | felsefe, mantık, etik, ahlak, epistemoloji |

Eşleşirse → `{course_id}_genel` üretilir (örn. `tyt_fizik_genel`).  
Eşleşme yoksa → boş liste, konu etiketsiz genel prompt kullanılır.

### 8.4 Sistemdeki Kullanım Alanları

Çıkarılan KC ID'ler aynı request döngüsünde 5 farklı yerde kullanılır:

```
KC ID'ler → ["matematik_turev_zincir_kurali"]
             │
             ├── [1] Content RAG filtresi
             │     curriculum_chunks WHERE kc_tags && ARRAY[kc_ids]
             │     → Sadece bu konuyla etiketlenmiş içerik getirilir
             │
             ├── [2] Mastery yükleme
             │     kc_mastery WHERE kc_id IN (kc_ids)
             │     → Bu konulardaki mevcut bilgi seviyeleri alınır
             │
             ├── [3] Misconception filtresi
             │     student_errors WHERE kc_id IN (kc_ids) AND resolved=false
             │     → Bu konulardaki çözülmemiş yanılgılar prompt'a eklenir
             │
             ├── [4] Session bağlamı (aktif konu takibi)
             │     ctx.active_kc_ids güncellenir
             │     → Sonraki request'te known_kc_ids olarak kullanılır
             │
             └── [5] Mastery güncelleme (etkileşim sonrası)
                   BKT update + kc_mastery UPSERT
                   chat_history.kc_tags olarak kaydedilir
```

### 8.5 Session Bağlamı — KC ID'ler Nasıl Taşınır?

```
Request 1: "Türev nedir?"
  → KC Mapper: ["matematik_turev_tanim"]
  → ctx.active_kc_ids = ["matematik_turev_tanim"]

Request 2: "Peki zincir kuralı?"  ← bağlam yok, tek başına anlamsız
  → KC Mapper: []  (soru çok kısa, konu çıkaramıyor)
  → Ama known_kc_ids = ["matematik_turev_tanim"]  (session'dan geliyor)
  → Sonuç: kc_ids = known + extracted = ["matematik_turev_tanim"]
  → Content RAG hâlâ türev konusundan içerik getirir ✓
```

---

## 10. Yanılgı Tespiti (Misconception Detector)

Öğrencinin yanlış kavramsal modeller kurduğunu tespit eder.

### Nasıl Çalışır?

```
Öğrenci: "Hız ile ivme aynı şeydir, ikisi de hareketi gösterir"
            │
            ▼
LLM analiz eder:
  "Bu mesajda açıkça yanlış bir kavram var mı?
   Varsa: {kc_id, açıklama} formatında döndür"
            │
            ▼
Yanılgı tespit edildi:
  kc_id: "fizik_kinematik_hız_ivme"
  description: "Hız ve ivmenin aynı kavram olduğunu düşünüyor.
                Hız: konum değişimi/zaman; İvme: hız değişimi/zaman"
            │
            ▼
student_errors tablosuna INSERT
```

### Promptlara Yansıması

Bir sonraki sohbette, o konuya ait **çözülmemiş yanılgılar** prompt'a eklenir:

```
## Dikkat Edilmesi Gereken Yanılgılar
- [fizik_kinematik] Hız ve ivmeyi aynı kavram sanıyor.
  Açıklarken bu farka özellikle değin.
```

LLM otomatik olarak bu yanılgıyı hedef alarak açıklama yapar.

---

## 11. Kişiselleştirme Sistemi

Her LLM çağrısı öncesinde 5 katman öğrenciye özgü veri toplanır. Aynı soruyu iki farklı öğrenci sorsa LLM farklı yanıt üretir.

### 5 Kişiselleştirme Katmanı

#### Katman 1 — Profil (`student_profiles` tablosu)

Her request'te PostgreSQL'den çekilir:

```
Öğrenci: Ahmet
Tercih ettiği açıklama stili: adım adım
Öğrenme hızı: yavaş
Bilinen zorluk alanları: matematik, fizik
```

`preferences` JSONB kolonu — worker zamanla günceller.  
Prompt'a `## Öğrenci Profili` başlığıyla eklenir.

#### Katman 2 — Mastery Snapshot (`mastery_scores` tablosu)

```
Türev Tanım:    ███████░░░ 72%  (Gelişiyor)
Zincir Kuralı: ████░░░░░░ 40%  (Gelişiyor)
İntegral:      ██░░░░░░░░ 20%  (Başlangıç)
```

Bu öğrencinin değerleri — başka öğrencide farklı.  
Aynı zamanda pedagoji stratejisi ve KC filter buradan belirlenir.

#### Katman 3 — Pedagoji Stratejisi

`avg_mastery` → hangi `.md` dosyasının yükleneceği.  
Detayı Bölüm 12'de.

#### Katman 4 — Yanılgılar (`student_errors` tablosu)

```
⚠ [fizik_kinematik] Hız ile ivmeyi aynı kavram sanıyor
⚠ [matematik_turev] Zincir kuralında çarpımı unutuyor
```

Bu öğrencinin tespit edilmiş yanlış kavramları — LLM bunları hedef alarak açıklar.  
`resolved=true` olan yanılgılar dahil edilmez.

#### Katman 5 — Semantik Hafıza (`chat_history` tablosu)

```python
search_learner_memory(
    learner_id=request.learner_id,   # sadece bu öğrencinin kayıtları
    query_embedding=query_embedding,  # mevcut soruyla semantik benzerlik
    top_k=3,
)
```

Bu öğrencinin tüm geçmiş oturumlarından mevcut soruyla en benzer 3 etkileşim.  
Başka öğrencinin hafızası kesinlikle karışmaz (`WHERE learner_id = :learner_id`).

---

### Veri Akışı

```
POST /api/chat  {"message": "Türev nedir?"}
      │
      ▼
[1] ProfileRetriever → student_profiles → Profil + preferences
[2] mastery_estimator → mastery_scores  → KCMasterySnapshot
[3] PedagogyPlanner  → avg_mastery      → diagnosis / reinforcement / practice / challenge
[4] MisconceptionStore → student_errors → Çözülmemiş yanılgılar
[5] search_learner_memory → chat_history → Top-3 benzer geçmiş
      │
      ▼
PromptBuilder → 8 katman birleştir → LLM'e gönder
```

Frontend sadece `message` + `session_id` gönderiyor.  
Kişiselleştirmenin tamamı backend tarafında bu öğrencinin DB kayıtlarından üretiliyor.

---

## 12. Pedagoji Planlayıcı

Öğrencinin mastery seviyesine göre hangi öğretim stratejisinin kullanılacağını seçer.

### Strateji Seçim Algoritması

```python
components = snapshot.components.values()

if not components:                    # Yeni öğrenci — hiç mastery kaydı yok
    strateji = "diagnosis"
    
avg_mastery = mean([c.p_mastery for c in components])

if avg_mastery < 0.4:
    strateji = "reinforcement"        # Temel kavramlar
elif avg_mastery < 0.7:
    strateji = "practice"             # Uygulama
else:
    strateji = "challenge"            # Analiz/Sentez
```

### Önkoşul Kontrolü

Bir konu için önkoşul konu belirlenmişse, önkoşulun mastery değeri de kontrol edilir:

```
Öğrenci "integral" soruyor (konu: tyt_matematik_integral)
Önkoşul: tyt_matematik_turev → p_mastery = 0.25

→ integral mastery'si 0.7 olsa bile
→ önkoşul zayıfsa strateji "practice"'e düşürülür
→ "Önce türeve dönelim" yönlendirmesi yapılır
```

### Strateji Dosyaları (`prompts/`)

#### `diagnosis.md` — Yeni öğrenci (mastery verisi yok)
```
- Öğrenci doğrudan soru sorduysa önce o soruyu yanıtla
- Yanıt sonunda hangi konuyu/sınavı çalıştığını tek soruyla sor
- Zorluk alanlarını bilmiyorsa "birlikte bakalım" tonuyla 2-3 kısa soru sor
- "Sınav yapacağım" değil, "birlikte görelim" havası koru
→ Sistem bu oturumdan ilk mastery sinyallerini toplamaya başlar
```

#### `reinforcement.md` — p_mastery < 0.4
```
- Temel tanımdan başla, karmaşık detaylara gitme
- Günlük hayattan somut örnekler kullan
- Adım adım ilerle
- Açıkladıktan sonra kısa kontrol sorusu ekle
```

#### `practice.md` — p_mastery 0.4–0.7
```
- "Anlat/nedir" sorularında kısa açıkla, ardından uygulama sorusu sor
- Öğrenci çözmeye çalışıyorsa ipucu ver, cevabı verme
- Yanlışta "Neredeyse doğru, şunu düşün:" ile yönlendir
```

#### `challenge.md` — p_mastery > 0.7
```
- İstisna durumları ve kenar vakaları sor
- Diğer konularla bağlantı kur
- "Başkasına nasıl anlatırsın?" diye sor
- Eleştirel düşünme gerektiren sorular sor
```

---

## 12. Prompt Oluşturma Sistemi (8 Katman)

Her LLM çağrısından önce bu katmanlar sırayla birleştirilir.

```
┌─────────────────────────────────────────────────────────┐
│ KATMAN 1: system_base.md                                │
│ "Sen kişiselleştirilmiş öğrenme asistanısın.            │
│  Sokratik yöntem kullan. Hazır cevap verme.             │
│  Bilgi seviyesine göre uyarla."                         │
├─────────────────────────────────────────────────────────┤
│ KATMAN 2: Pedagoji Direktifi (dinamik)                  │
│ [reinforcement.md / practice.md / challenge.md]         │
├─────────────────────────────────────────────────────────┤
│ KATMAN 3: Öğrenci Profili                               │
│ "Öğrenci: Ahmet                                         │
│  Açıklama stili: adım adım                              │
│  Öğrenme hızı: orta"                                    │
├─────────────────────────────────────────────────────────┤
│ KATMAN 4: Mastery Snapshot (görsel)                     │
│ "Türev Tanım:    ███████░░░ 72%  (Gelişiyor)            │
│  Zincir Kuralı: ████░░░░░░ 40%  (Gelişiyor)            │
│  İntegral:      ██░░░░░░░░ 20%  (Başlangıç)"           │
├─────────────────────────────────────────────────────────┤
│ KATMAN 5: Aktif Yanılgılar                              │
│ "⚠ Zincir kuralında çarpımı unutuyor                   │
│  ⚠ Türev ile fonksiyonu karıştırıyor"                  │
├─────────────────────────────────────────────────────────┤
│ KATMAN 6: Semantik Hafıza (Memory RAG)                  │
│ "[Geçmiş] Öğrenci limit kavramını anladı               │
│  [Geçmiş] Türev tanımında zorlandı, örnek istedi"       │
├─────────────────────────────────────────────────────────┤
│ KATMAN 7: İçerik RAG                                    │
│ "[TYT Matematik - Türev] Türev, bir fonksiyonun         │
│  x noktasındaki anlık değişim hızıdır. f'(x) = ..."    │
├─────────────────────────────────────────────────────────┤
│ KATMAN 8: Konuşma Geçmişi (son 6 mesaj)                │
│ user: "türev nedir?"                                    │
│ assistant: "Anlık değişim hızı..."                      │
│ user: "peki zincir kuralı?"                             │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
              LLM'e gönderilir
```

---

## 13. RAG Sistemi (Retrieval-Augmented Generation)

LLM'in "kendi bilgisiyle" değil, **sisteme yüklenen ders içerikleriyle** cevap vermesini sağlar. Halüsinasyon riskini azaltır.

### 13.1 İçerik İndeksleme (Bir Kez — PDF Yüklendiğinde)

```
1. PDF / doküman  →  /api/upload  endpoint'ine gönderilir
        ↓
2. ingestion_pipeline.py → IngestionPipeline.ingest_pdf()
   pypdf ile sayfa sayfa metin çıkarılır, sayfalar \n\n ile birleştirilir
        ↓
3. Chunker.chunk(text)  [max_chars=1500, overlap_chars=150]
   ┌─ Adım 1: Markdown başlıklarında böl (h1/h2/h3)
   │           Her başlık → ayrı bölüm + heading etiketi
   ├─ Adım 2: Bölüm > 1500 karakter ise paragraflara böl (\n\n sınırı)
   │           Paragraf > 1500 karakter ise cümlelere böl (.!? sınırı)
   └─ Adım 3: Overlap uygula
               Her chunk'ın başına önceki chunk'ın son 150 karakteri eklenir
               → Bağlamın chunk sınırında kopmaması için
        ↓
4. embed_batch() — tüm chunk'lar tek API çağrısıyla embed edilir
   BGE-M3 (baai/bge-m3, Novita) → 1024-boyutlu float vektör
        ↓
5. curriculum_chunks tablosuna INSERT
   { document_id, chunk_index, content, embedding, kc_tags, metadata{heading} }
        ↓
6. HNSW index otomatik güncellenir (m=16, ef_construction=64)
   → cosine search O(log n) hızında çalışır
```

**Chunker parametreleri:**

| Parametre | Değer | Açıklama |
|---|---|---|
| `max_chars` | 1500 | Bir chunk'ın maksimum karakter uzunluğu |
| `overlap_chars` | 150 | Her chunk'a önceki chunk'tan eklenen örtüşme |
| Bölme önceliği | başlık → paragraf → cümle | Yapıya saygılı hiyerarşik bölme |

---

### 13.2 Arama Motoru — Hybrid Search + RRF

Kullanıcı her mesaj gönderdiğinde `search_content()` iki farklı arama yöntemi çalıştırır ve sonuçları birleştirir.

#### Adım 1 — Sorguyu Embed Et

```
user_message: "Türkiye'nin iklim kuşakları nelerdir?"
      ↓
BGE-M3 embedder → [0.021, -0.134, 0.089, ...] (1024 float)
      ↓
Bu vektör hem içerik aramasında hem hafıza aramasında kullanılır
(sadece bir kez embed edilir — performans için)
```

#### Adım 2 — Dense Search (Semantik Arama)

```sql
SELECT id, row_number() OVER (ORDER BY embedding <=> query_vector) AS rank
FROM curriculum_chunks
[WHERE kc_tags && ARRAY['coğrafya_iklim']::text[]]   -- KC filter varsa
LIMIT 50
```

- `<=>` operatörü: pgvector cosine distance
- HNSW index devreye girer → yaklaşık en yakın komşu araması
- Anlam benzerliğini yakalar: "sıcaklık kuşağı" → "iklim bölgesi" eşleşir

#### Adım 3 — Sparse Search (Metin Benzerliği)

```sql
SELECT id, row_number() OVER (ORDER BY similarity(content, query_text) DESC) AS rank
FROM curriculum_chunks
[WHERE kc_tags && ARRAY['coğrafya_iklim']::text[]]
LIMIT 50
```

- `similarity()`: PostgreSQL `pg_trgm` uzantısı — trigram tabanlı karakter örtüşmesi
- Tam anahtar kelime eşleşmelerini yakalar: "Akdeniz iklimi" → "Akdeniz iklimi"
- Dense'in kaçırdığı teknik terimleri, özel isimleri yakalar

#### Adım 4 — RRF Birleştirme (Reciprocal Rank Fusion)

İki listedeki sıralamaları ağırlıklı olarak birleştirir:

```
rrf_score = 1/(60 + dense_rank) + 1/(60 + sparse_rank)

Örnek:
  chunk_A → dense_rank=1,  sparse_rank=5  → 1/61 + 1/65 = 0.0316
  chunk_B → dense_rank=3,  sparse_rank=1  → 1/63 + 1/61 = 0.0322
  chunk_C → dense_rank=2,  sparse_rank=10 → 1/62 + 1/70 = 0.0304

  Sıralama: B > A > C
  → Her iki aramada da iyi sıralanan chunk öne çıkar
  → Sadece bir yöntemde iyi olan chunk cezalandırılmaz
```

Sabit `60`: Sıralamadaki küçük farkların etkisini yumuşatır (k=60 RRF standardı).

#### Adım 5 — KC Filter (Opsiyonel)

```
Oturumda aktif konu: ["coğrafya_iklim", "coğrafya_türkiye"]
      ↓
WHERE kc_tags && ARRAY['coğrafya_iklim', 'coğrafya_türkiye']::text[]
      ↓
Sadece bu konuya etiketlenmiş chunk'lar aranır
→ Alakasız derslerin içerikleri prompt'a girmez
```

#### Adım 6 — Reranker (Opsiyonel)

```
ContentRetriever'a Reranker bağlıysa:
  top-5 chunk → cross-encoder modele gönderilir
  → Her chunk için (query, chunk) çifti skorlanır
  → Yeniden sıralanır
  → Daha hassas ama yavaş
```

#### Tam Akış Özeti

```
user_message
    │
    ▼  [embed — 1 kez]
query_embedding (1024d)
    │
    ├──► [Dense] curriculum_chunks WHERE kc_filter  ORDER BY embedding <=> query  LIMIT 50
    │
    └──► [Sparse] curriculum_chunks WHERE kc_filter  ORDER BY similarity(content, query)  LIMIT 50
              │
              ▼
         [RRF Fusion]  1/(60+rank_d) + 1/(60+rank_s)  →  TOP-K sıralama
              │
              ▼
         [Reranker?]  cross-encoder re-score  (varsa)
              │
              ▼
         top-5 RetrievedChunk
         { document_id, chunk_index, content, heading, kc_tags }
              │
              ▼
         to_prompt_context()
         "--- Kaynak 1 (tyt_biyoloji) ---
          [Hücre Bölünmesi] Mitoz bölünme..."
              │
              ▼
         Prompt Katman 7'ye eklenir → LLM'e gönderilir
```

---

### 13.2.1 Somut Örnek: "biyolojide solunum sistemini anlat" Sorusu

Öğrenci bu mesajı gönderdiğinde sistemin içinde tam olarak şu adımlar gerçekleşir:

```
Kullanıcı mesajı: "biyolojide solunum sistemini detaylı anlatır mısın"
```

**Adım 1 — KC Mapper (LLM)**
```
LLM'e gönderilir: "Bu sorudan konu kodları çıkar."
LLM döndürür: ["tyt_biyoloji_solunum_sistemi"]
```
Bu `kc_id` hem mastery sorgusu hem de RAG filtresi olarak kullanılır.

**Adım 2 — Paralel Embed**
```
BGE-M3 modeli mesajı embed eder:
  "biyolojide solunum sistemini detaylı anlatır mısın"
  → [0.031, -0.087, 0.142, ...] (1024 float)

Bu vektör bir kez üretilir; hem Content RAG hem Memory RAG paylaşır.
```

**Adım 3 — Dense Search (Semantik)**
```sql
WITH dense_search AS (
    SELECT id, row_number() OVER (
        ORDER BY embedding <=> '[0.031, -0.087, 0.142, ...]'::vector
    ) AS rank
    FROM curriculum_chunks
    WHERE kc_tags && ARRAY['tyt_biyoloji_solunum_sistemi']::text[]
    LIMIT 50
)
```
Vektör uzayında "solunum", "akciğer", "alveol", "gaz alışverişi" gibi kavramları içeren
chunk'lar öne çıkar — soru kelimesiyle birebir eşleşme olmasa da anlam yakınlığı yeterli.

**Adım 4 — Sparse Search (Trigram)**
```sql
WITH sparse_search AS (
    SELECT id, row_number() OVER (
        ORDER BY similarity(content, 'biyolojide solunum sistemini detaylı anlatır mısın') DESC
    ) AS rank
    FROM curriculum_chunks
    WHERE kc_tags && ARRAY['tyt_biyoloji_solunum_sistemi']::text[]
    LIMIT 50
)
```
"solunum" kelimesini birebir içeren chunk'lar öne çıkar. Dense'in kaçırabileceği
"Solunum Sistemi Bileşenleri" başlıklı bölümler bu yolla yakalanır.

**Adım 5 — RRF Birleştirme**
```
Örnek sonuç:
  chunk_A [Solunum Sistemi — Genel]        dense=1, sparse=1 → 1/61 + 1/61 = 0.0328  ← En yüksek
  chunk_B [Alveol Yapısı ve Gaz Değişimi]  dense=2, sparse=4 → 1/62 + 1/64 = 0.0317
  chunk_C [Hava Yolları — Trake, Bronş]    dense=3, sparse=2 → 1/63 + 1/62 = 0.0320
  chunk_D [Solunum Kasları ve Mekanizma]   dense=5, sparse=3 → 1/65 + 1/63 = 0.0312
  chunk_E [BKT Dış Solunum vs İç Solunum] dense=4, sparse=7 → 1/64 + 1/67 = 0.0306

Top-5 sıralama: A > C > B > D > E
```
İki aramada da tutarlı olan chunk'lar (A, C) öne geçer.

**Adım 6 — Prompt'a Dönüşüm**
```
to_prompt_context() çıktısı (Prompt Katman 7):

İlgili kaynak içeriği:

--- Kaynak 1 (tyt_biyoloji) ---
[Solunum Sistemi — Genel] Solunum sistemi, vücudun oksijen alıp
karbondioksit vermesini sağlayan organlar bütünüdür. Burun, yutak,
gırtlak, soluk borusu, bronşlar ve akciğerlerden oluşur...

--- Kaynak 2 (tyt_biyoloji) ---
[Hava Yolları] Trake (soluk borusu) C şeklinde kıkırdak halkalarla...

--- Kaynak 3 (tyt_biyoloji) ---
[Alveol Yapısı] Her alveol tek katlı yassı epitel...
(+ 2 chunk daha)
```

**Özet:** LLM bu 5 chunk'ı "hafıza" olarak kullanarak yanıt üretir.
Eğer PDF'e solunum sistemi içeriği yüklenmemişse chunk'lar boş gelir
ve `to_prompt_context()` boş string döner — LLM kendi genel bilgisiyle devam eder.

---

### 13.3 Semantik Hafıza RAG — Content RAG ile Karşılaştırma

İki sistem aynı embedding altyapısını kullanır ama tamamen farklı tablolara, farklı amaçlarla bakar.

| | Content RAG | Memory RAG |
|---|---|---|
| Tablo | `curriculum_chunks` | `chat_history` |
| İçerik | Admin'in yüklediği PDF/dokümanlar | Bu öğrencinin geçmiş konuşma özetleri |
| Kime ait | Herkese ortak | Sadece o öğrenciye özgü |
| Ne zaman yazılır | PDF yüklendiğinde (bir kez) | Her chat'ten sonra arka planda |
| Arama yöntemi | Hybrid (dense + sparse + RRF) | Dense only (cosine) |
| Prompt'a katkısı | Katman 7 — ders içeriği | Katman 6 — geçmiş bağlam |

---

### 13.4 Hafıza Yazma Akışı (Write Path)

Her chat yanıtından sonra Redis kuyruğuna atılır, worker arka planda işler — kullanıcıyı bekletmez.

```
LLM yanıtı kullanıcıya döner
        ↓
Redis kuyruğuna push (fire-and-forget):
  content_summary = "S: {kullanıcı sorusu[:500]}\nY: {LLM yanıtı[:1500]}"
        ↓
Worker → InteractionLogger.log()
  content_summary embed edilir → BGE-M3 → 1024d vektör
        ↓
chat_history tablosuna INSERT:
  { learner_id, session_id, interaction_type,
    content_summary, embedding, kc_tags, correctness }
        ↓
aynı transaction içinde:
  - Yeni yanılgılar → student_errors INSERT
  - LLM mastery değerlendirmesi → mastery_scores UPSERT
  - 10 etkileşimde bir → reflection üret → student_profiles.preferences güncelle
  - Hallucination kontrolü → log'a yaz
        ↓
session.commit()
```

> **Neden soru+yanıt birlikte?**  
> Memory RAG sadece "öğrenci ne sormuş?" değil, "asistan o konuyu nasıl açıklamış?" bilgisini de döndürür.  
> LLM daha önce verdiği açıklamayı tekrarlamamak veya üzerine inşa etmek için bu bağlamı kullanır.

**`interaction_type` değerleri:**
```
"question"          — kullanıcı soru sordu
"misconception"     — yanlış kavram tespit edildi
"success"           — konu doğru anlaşıldı
"struggle"          — zorlanma tespit edildi
"reflection"        — periyodik öğrenme özeti
```

---

### 13.5 Hafıza Okuma Akışı (Read Path)

Her request'te `query_embedding` zaten üretilmiş olduğu için ek embed maliyeti yoktur.

```python
# chat_orchestrator.py — sadece bir kez embed edilir
query_embedding = await embedder.embed(user_message)

# Content RAG — curriculum_chunks, herkese aynı
content_chunks = await retriever.retrieve(
    query=user_message,
    embedding=query_embedding,
    kc_filter=active_kc_ids,
    top_k=5,
)

# Memory RAG — chat_history, sadece bu öğrenci
memory = await vector_store.search_learner_memory(
    learner_id=request.learner_id,    # ← kişiye özgü WHERE filtresi
    query_embedding=query_embedding,
    top_k=3,
)
```

```sql
-- Memory RAG SQL
SELECT *
FROM chat_history
WHERE learner_id = :learner_id          -- başkasının hafızası kesinlikle karışmaz
ORDER BY embedding <=> :query_embedding -- cosine distance
LIMIT 3
```

İki sorgu da sıralı çalışır (asyncpg aynı bağlantıda eş zamanlı sorguyu desteklemez).

```
Örnek: Öğrenci "türev nedir?" soruyor
  Content RAG → curriculum_chunks'tan "Türev" bölümleri (PDF içeriği)
  Memory RAG  → bu öğrencinin geçmişinden:
    [Geçmiş-1] 2 gün önce: "türev tanımı nedir?" — QUESTION
    [Geçmiş-2] Dün: "zincir kuralında hata yaptı" — MISCONCEPTION
  → LLM hem ders kaynağına hem öğrencinin geçmişine bakarak yanıt üretir
```

---

## 14. Quiz Sistemi

İki farklı quiz modu var: **Soru Bankası Quiz** (admin tarafından hazırlanmış statik sorular) ve **LLM Adaptif Quiz** (mastery'ye göre dinamik üretilen sorular). Her ikisi de aynı mastery güncelleme mekanizmasını kullanır.

---

### 14.1 Soru Bankası Araması — `GET /api/quiz/subjects`

Kullanıcıya gösterilecek konu listesini oluşturur. **Bank-first yaklaşım:** `question_bank` kaynak gerçek, mastery verileri üzerine eşlenir.

#### Algoritma

```
1. question_bank'taki tüm kc_id'leri çek (kaynak gerçek)
   SELECT kc_id, count(*) FROM question_bank GROUP BY kc_id
   → bank = {"tyt_felsefe": 188, "tyt_biyoloji": 245, ...}

2. Her bank kc_id için "çekirdek ders" türet (_core_subject):
   "tyt_felsefe" → "felsefe"
   "tyt_biyoloji" → "biyoloji"
   bank_core_map = {"felsefe": "tyt_felsefe", "biyoloji": "tyt_biyoloji", ...}

3. Öğrencinin mastery_scores kayıtları:
   SELECT kc_id, p_mastery FROM mastery_scores WHERE learner_id = :lid

4. Her mastery kc_id'yi bank'a eşle:
   "felsefe_zor_konular_detayli" → core="felsefe" → bank_kc="tyt_felsefe" ✓
   "matematik_turev_tanim"       → core="matematik" → bank_kc="tyt_matematik" ✓
   "xyz_bilinmeyen"              → core="xyz" → bank'ta yok → question_count=0 ile listele

5. Sonuç: tüm bank konuları + sadece mastery'de olan konular (soru sayısı 0)
```

Sıralama:
```
1. Sorusu olan konular önce → mastery yüksekten düşüğe (önce çalışılması gerekenler)
2. Sorusu olmayan (sadece mastery'de) konular sona
```

**Yeni kullanıcı** (mastery yok): Sadece bank konuları mastery=null ile listelenir.

---

### 14.2 Soru Bankası Quiz — `GET /api/quiz/bank-quiz`

Seçilen konudan rastgele soru çeker ve `quiz_sessions`'a oturum kaydı oluşturur. **Embedding yok, LLM yok — saf SQL.**

```sql
-- Sorular
SELECT id, question_text, options
FROM question_bank
WHERE kc_id ILIKE '%tyt_biyoloji%'   -- ILIKE: büyük/küçük harf duyarsız, kısmi eşleşme
ORDER BY random()                      -- Her seferinde farklı sorular
LIMIT 10                               -- max 20

-- Quiz session kaydı
INSERT INTO quiz_sessions (id, learner_id, kc_id, status)
VALUES (:session_id, :learner_id, :kc_id, 'active')
```

- `ILIKE '%kc_id%'`: Tam eşleşme değil, içerme araması — `tyt_biyoloji_hücre` ve `tyt_biyoloji_mitoz` ikisi de `tyt_biyoloji` aramasına döner
- `random()`: PostgreSQL'in rastgele sıralama fonksiyonu — her çağrıda farklı sorular gelir
- Correct answer **frontend'e gönderilmez** (`BankQuestionOut` sadece question + options içerir — kopya çekmeyi önler)
- `quiz_session_id` response'a eklenerek frontend'e döner; cevap gönderimde `quiz_answers` kaydı için kullanılır

---

### 14.3 Cevap Kontrolü — `POST /api/quiz/bank-answer`

```
Kullanıcının seçtiği şık
    │
    ▼
SELECT correct_answer, explanation
FROM question_bank
WHERE id = :question_id
    │
    ▼
is_correct = (selected.strip() == correct_answer.strip())
    ← Tam string karşılaştırma (büyük/küçük harf ve boşluk normalize edilir)
    │
    ▼
new_mastery belirlenir:
  is_correct=True  → 0.85  (yüksek güven sinyali)
  is_correct=False → 0.15  (düşük güven sinyali)
    │
    ▼
fire_and_forget(new_mastery={kc_id: 0.85})
    │
    ▼
Worker → BKT soft update:
  p_new = p_old + 0.2 × (0.85 − p_old)
    │
    ▼
mastery_scores UPSERT → profil güncellenir
```

---

### 14.4 LLM Adaptif Quiz — `POST /api/quiz/generate-adaptive`

Statik sorudan farklı: **mastery seviyesine göre zorluk** belirler, sonra RAG + few-shot ile LLM'e soru **ürettir**.

#### Adım 1 — Mastery'yi Oku

```sql
SELECT p_mastery FROM mastery_scores
WHERE learner_id = :lid AND kc_id = :kc
```

Kayıt yoksa varsayılan: `mastery = 0.3`

#### Adım 2 — Zorluk Seviyesi Belirle

```
mastery < 0.30 → "çok kolay (temel kavram sorusu)"
mastery < 0.50 → "kolay (kavramsal anlama sorusu)"
mastery < 0.70 → "orta (uygulama sorusu)"
mastery < 0.90 → "zor (analiz/sentez sorusu)"
mastery ≥ 0.90 → "çok zor (değerlendirme/eleştirel düşünme sorusu)"
```

#### Adım 3 — RAG ile Bağlam Topla

```
curriculum_chunks'ta kc_id filtreli Hybrid Search (top-3)
      ↓
İlgili ders içeriği (prompt context)
```

#### Adım 4 — Few-Shot Örnek Çek

```sql
SELECT question_text, options, correct_answer, explanation
FROM question_bank
WHERE kc_id = :kc_id
ORDER BY random()
LIMIT 1
```

Bu örnek soru LLM'e şöyle iletilir:
```
[DİKKAT: Aşağıdaki kazanım sorusunu ÖRNEK al, onun yapısını ve
 zorluğunu taklit ederek konuyla ilgili YENİ ve FARKLI bir soru üret:]
{ "question": "...", "options": [...], "correct_answer": "...", "explanation": "..." }
```

#### Adım 5 — LLM'e Gönder

```
Prompt = ders_içeriği + örnek_soru + zorluk_direktifi + mastery_%
      ↓
QuizGenerator → LLM
      ↓
{ question_text, options[4], correct_answer, explanation }
      ↓
quiz_sessions tablosuna kaydedilir
      ↓
Frontend'e döner (correct_answer dahil — cevap gösterilir)
```

#### Tam Karşılaştırma: Bank Quiz vs Adaptif Quiz

| Özellik | Bank Quiz | Adaptif Quiz |
|---|---|---|
| Soru kaynağı | question_bank (statik) | LLM üretir (dinamik) |
| Zorluk | Sabit (difficulty kolonu) | mastery'ye göre otomatik |
| Arama yöntemi | `ILIKE + random()` | RAG + few-shot LLM |
| Hız | Hızlı (saf SQL) | Yavaş (LLM çağrısı) |
| Tekrar | Aynı sorular gelebilir | Her seferinde yeni soru |
| Kullanım | Alıştırma | Kişiselleştirilmiş sınav |

---

## 15. Profil Sayfası Veri Akışı

```
GET /api/profile/{learner_id}
        │
        ▼
mastery_scores tablosundan tüm kayıtlar çekilir (ORM)
        │
Her kayıt için domain türetilir:
  subject="Genel" veya NULL → kc_id prefix kullanılır
  subject="tyt_matematik"   → "matematik"
  subject="coğrafya"        → "coğrafya"
        │
Okunabilir label üretilir:
  kc_id: "tyt_matematik_turev_zincir"
  domain: "matematik"
  label: "Turev Zincir" (prefix'ler çıkarılır)
        │
Derse göre gruplandırılır ve sıralanır
        │
Frontend'e gönderilir:
  {
    "mastery_by_subject": {
      "Matematik": [
        {"kc_id": "...", "label": "Türev Zincir", "p_mastery": 0.72, "attempts": 8}
      ],
      "Felsefe": [...]
    }
  }
        │
        ▼
Frontend görselleri:
  - Radar chart (≥3 ders varsa)
  - Her ders için progress bar + renk kodu
  - Her konu için seviye rozeti (Başlangıç / Gelişiyor / Uzman)
```

---

## 16. Tam Veri Akışı — Tek Bakışta

```
┌──────────────────────────────────────────────────────────────┐
│  Öğrenci: "Türkiye'nin iklimi nasıl açıklanır?"              │
└─────────────────────┬────────────────────────────────────────┘
                      │ POST /api/chat
                      ▼
        ┌─────────────────────────────────┐
        │          API SERVER              │
        │                                  │
        │  Redis   → Oturum geçmişi        │
        │  pgvect. → Ders içeriği (top-5)  │
        │  pgvect. → Geçmiş etkileşim (3)  │
        │  LLM     → kc: coğrafya_iklim    │
        │  DB      → p_mastery: 0.30       │
        │  Strateji: reinforcement          │
        │  Prompt: 8 katman                 │
        │  LLM     → Yanıt üret            │
        │  Redis   → Geçmişe ekle          │
        └──────────────┬──────────────────┘
                       │ Yanıt kullanıcıya döner (anlık)
                       │
                       │ + Redis kuyruğuna iş atılır
                       ▼
        ┌─────────────────────────────────┐
        │            WORKER               │
        │  (Kullanıcı beklemez)           │
        │                                  │
        │  embed → pgvector kaydet         │
        │  LLM mastery değerlendir: 0.45  │
        │  BKT: 0.30 → 0.33              │
        │  mastery_scores UPSERT          │
        │  commit()                        │
        └─────────────────────────────────┘
                       │
          Bir sonraki soruda etki:
          ✓ Profil: "Coğrafya %33" görünür
          ✓ Quiz:   "coğrafya" konusu listelenir
          ✓ Prompt: mastery snapshot güncellenir
          ✓ Strateji: hâlâ reinforcement modu
```

---

## 17. API Endpoint Özeti

| Endpoint | Yöntem | Açıklama |
|---|---|---|
| `/api/auth/register` | POST | Yeni kullanıcı kaydı |
| `/api/chat` | POST | Sohbet mesajı — ana öğrenme döngüsü |
| `/api/profile/{id}` | GET | Profil + mastery bilgisi |
| `/api/profile/{id}` | PATCH | Profil güncelle |
| `/api/profile/{id}` | DELETE | Kullanıcıyı tüm verileriyle sil |
| `/api/quiz/subjects` | GET | Kullanıcının dinamik konu listesi |
| `/api/quiz/bank-quiz` | GET | Soru bankasından N soru çek |
| `/api/quiz/bank-answer` | POST | Cevap gönder → mastery güncelle |
| `/api/quiz/generate-adaptive` | POST | Mastery'ye göre LLM quiz sorusu üret |
| `/api/quiz/questions` | POST | Admin: tek soru ekle |
| `/api/quiz/questions/upload` | POST | Admin: toplu JSON yükle |
| `/api/conversations` | GET | Konuşma listesi |
| `/api/conversations/{id}/messages` | GET | Mesaj geçmişi |
| `/api/admin/stats` | GET | Sistem istatistikleri |
| `/api/admin/hallucination-logs` | GET | Halüsinasyon kayıtları |
| `/api/upload` | POST | PDF / doküman yükle |

---

## 18. Konfigürasyon

### Öncelik Sırası
```
Ortam değişkeni  >  config.json  >  .env dosyası  >  Varsayılan
```

### Önemli `.env` Değişkenleri

| Değişken | Açıklama |
|---|---|
| `NOVITA_API_KEY` | LLM + Embedding API anahtarı |
| `POSTGRES_HOST` | Supabase DB host |
| `POSTGRES_PASSWORD` | DB şifresi |
| `SUPABASE_JWT_SECRET` | Token doğrulama anahtarı |
| `REDIS_URL` | Redis bağlantı adresi |
| `LLM_PROVIDER` | "novita" / "openai" / "anthropic" |

### `config.json` Parametreleri

| Alan | Değer | Açıklama |
|---|---|---|
| `llm.novita_model` | deepseek/deepseek-v3.2 | Sohbet için kullanılan LLM |
| `embedder.model` | BAAI/bge-m3 | Embedding modeli |
| `embedder.dim` | 1024 | Vektör boyutu |
| `pedagogy.mastery_threshold_low` | 0.4 | Başlangıç/Gelişiyor sınırı |
| `pedagogy.mastery_threshold_high` | 0.7 | Gelişiyor/Uzman sınırı |
| `retrieval.content_top_k` | 5 | RAG'dan kaç içerik parçası alınır |
| `retrieval.memory_top_k` | 3 | Hafızadan kaç geçmiş etkileşim alınır |
| `redis.session_ttl_seconds` | 3600 | Oturum süresi (1 saat) |

---

*Son güncelleme: Mayıs 2026 · Tüm bileşenler production'da aktif*

---

## Supabase Tablo Özeti

| Tablo | Açıklama | Yazan | Okuyan |
|---|---|---|---|
| `student_profiles` | Öğrenci kimlik + preferences | ProfileRetriever | PromptBuilder, PedagogyPlanner |
| `mastery_scores` | KC bazında bilgi seviyesi 0–1 | Worker (BKT update) | MasteryEstimator, QuizSubjects |
| `curriculum_chunks` | PDF içerik parçaları + vektör | IngestionPipeline | ContentRetriever (RAG) |
| `chat_history` | Her etkileşim özeti + vektör | Worker (InteractionLogger) | Memory RAG (top-3 cosine) |
| `student_errors` | LLM tespit ettiği yanılgılar | Worker (MisconceptionStore) | PromptBuilder (aktif yanılgılar) |
| `question_bank` | Admin'in yüklediği TYT/AYT soruları | Admin endpoint | BankQuiz, AdaptiveQuiz (few-shot) |
| `quiz_sessions` | Quiz oturumu kaydı | BankQuiz + AdaptiveQuiz | QuizStore |
| `quiz_questions` | LLM üretilen quiz soruları | AdaptiveQuiz | QuizStore |
| `quiz_answers` | Öğrencinin cevapları | BankAnswer endpoint | QuizStore (skor hesaplama) |
