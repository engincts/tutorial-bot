# Tutor Bot — Mimari Dokümantasyonu

## 1. Genel Bakış

**Tutor Bot**, adaptif öğrenme uygulayan kişiselleştirilmiş bir yapay zeka öğrenci asistanıdır:

- Gerçek zamanlı bilgi takibi (Knowledge Tracing) ile öğrenci seviyesini ölçer
- RAG (Retrieval-Augmented Generation) ile müfredat içeriği getirir
- Hakimiyet düzeyine göre pedagojik strateji seçer (scaffold / practice / challenge)
- Kavram yanılgılarını tespit edip kaydeder
- Öğrenci geçmişi ve mastery profilini kalıcı olarak saklar

### Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| API | FastAPI + Uvicorn (async) |
| Auth | Supabase (JWT doğrulama) |
| Veritabanı | PostgreSQL 16 + pgvector (HNSW index) |
| Cache / Queue | Redis 7 |
| LLM | OpenAI / Anthropic / Novita (yapılandırılabilir) |
| Embedding | BGE-M3 / OpenAI / Novita (yapılandırılabilir) |
| Knowledge Tracing | AKT / DKT (saf Python, PyTorch gerektirmez) |
| ORM | SQLAlchemy 2.0 async |
| Monitoring | Prometheus Metrics + JSON Structured Logging |
| Proxy | Nginx (SSE & SSL support) |
| CI/CD | GitHub Actions + Docker Multi-stage |

---

## 2. Dizin Yapısı

```
tutor-bot/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── auth.py                    # POST /auth/register, /auth/login
│   │   │   ├── chat.py                    # POST /chat, /chat/stream (SSE)
│   │   │   ├── quiz.py                    # POST /quiz/* (adaptive, batch)
│   │   │   ├── ingest.py                  # POST /ingest/text, /ingest/pdf
│   │   │   ├── profile.py                 # GET /profile/{id}
│   │   │   ├── admin.py                   # GET /admin/* (monitoring, logs)
│   │   │   ├── export.py                  # GET /export/* (csv, json)
│   │   │   ├── upload.py                  # POST /upload (student docs)
│   │   │   └── session.py                 # POST /session/reset
│   │   ├── middleware/
│   │   │   ├── metrics.py                 # Prometheus HTTP & Business metrics
│   │   │   └── tracing.py                 # X-Request-ID propagation
│   │   ├── dependencies.py                # FastAPI Depends() singleton fabrikaları
│   │   └── dependencies_auth.py           # Bearer token → learner_id
│   │
│   ├── domain/                            # Saf Python domain modelleri (ORM yok)
│   │   ├── learner_profile.py             # LearnerProfile, tercihler
│   │   ├── interaction.py                 # Interaction, Misconception, InteractionType
│   │   ├── session_context.py             # SessionContext, TurnRecord
│   │   └── knowledge_component.py        # KnowledgeComponent, KCMasterySnapshot
│   │
│   ├── services/
│   │   ├── orchestration/
│   │   │   ├── chat_orchestrator.py       # /chat isteğini koordine eder (Sync & SSE)
│   │   │   ├── session_manager.py         # Redis oturum CRUD
│   │   │   ├── pedagogy_planner.py        # Strateji seçimi (mastery eşikleri)
│   │   │   ├── prompt_builder.py          # System + context prompt birleştirme
│   │   │   ├── conversation_summarizer.py # Context window koruma (özetleme)
│   │   │   ├── correctness_evaluator.py   # LLM ile doğruluk değerlendirmesi → KT sinyali
│   │   │   └── misconception_detector.py  # LLM ile kavram yanılgısı tespiti
│   │   │
│   │   ├── content_rag/
│   │   │   ├── chunker.py                 # Yapı-farkındalıklı metin bölme
│   │   │   ├── ingestion_pipeline.py      # Metin/PDF → chunk → embedding → pgvector
│   │   │   ├── retriever.py               # Semantik arama (curriculum_chunks)
│   │   │   └── reranker.py                # Opsiyonel LLM tabanlı chunk yeniden sıralama
│   │   │
│   │   ├── learner_memory/
│   │   │   ├── profile_retriever.py       # student_profiles + mastery_scores ORM
│   │   │   ├── interaction_logger.py      # Etkileşim embed et → chat_history pgvector
│   │   │   ├── memory_updater.py          # Yanıt sonrası async DB yazmaları
│   │   │   └── misconception_store.py     # student_errors tablosu CRUD
│   │   │
│   │   └── knowledge_tracing/
│   │       ├── base.py                    # BaseKnowledgeTracer arayüzü
│   │       ├── kc_mapper.py               # LLM: sorgudan KC ID'leri çıkar
│   │       ├── akt_model.py               # AKT (monotonic attention decay)
│   │       ├── dkt_model.py               # DKT (Bayesian Knowledge Tracing formülleri)
│   │       └── mastery_estimator.py       # KCMapper + Tracer koordinasyonu
│   │
│   ├── infrastructure/
│   │   ├── database.py                    # SQLAlchemy async engine/session fabrikaları
│   │   ├── auth.py                        # JWT decode (base64 → UUID)
│   │   ├── redis_client.py                # SessionCache + WorkerQueue
│   │   ├── event_bus.py                   # Redis Pub/Sub (events:mastery_change vb.)
│   │   ├── pg_vector_store.py             # ORM: ContentChunk, InteractionEmbedding
│   │   ├── embedder_factory.py            # BGEM3Embedder, OpenAIEmbedder, NovitaEmbedder
│   │   └── llm/
│   │       ├── base.py                    # BaseLLMClient, Message, LLMResponse
│   │       ├── openai_client.py           # OpenAI async istemcisi
│   │       ├── anthropic_client.py        # Anthropic async istemcisi
│   │       └── novita_client.py           # Novita (OpenAI uyumlu) async istemcisi
│   │
│   ├── worker/
│   │   └── post_response_worker.py        # Uzun çalışan süreç: Redis kuyruğu → DB
│   │
│   ├── main.py                            # FastAPI uygulama fabrikası, lifespan
│   ├── settings.py                        # Pydantic Settings (env vars + config.json)
│   ├── config_loader.py                   # Özel JSON config kaynağı
│   ├── logging_json.py                    # Production için JSON Formatter
│   ├── i18n.py                            # Çok dilli prompt desteği (TR/EN)
│   └── logging_config.py                  # Log seviyesi yapılandırması
│
├── migrations/                            # Alembic şema versiyonlama
├── prompts/                               # Markdown prompt şablonları
│   ├── system_base.md                     # Temel sistem talimatı
│   ├── reinforcement.md                   # mastery < 0.4 (scaffold)
│   ├── practice.md                        # 0.4 ≤ mastery < 0.7 (guided)
│   └── challenge.md                       # mastery ≥ 0.7 (extend)
│
├── scripts/                               # Seed data, değerlendirme araçları
├── tests/                                 # Birim + entegrasyon testleri
├── config.json                            # Gizli olmayan ayarlar (JSON)
├── .env.example                           # Ortam değişkeni şablonu
├── docker-compose.yml                     # PostgreSQL + pgvector + Redis
├── pyproject.toml                         # Proje metadata + bağımlılıklar
└── requirements.txt                       # Sabitlenmiş bağımlılık versiyonları
```

---

## 3. Veritabanı Şeması

### `curriculum_chunks` — Müfredat vektör deposu

```sql
id            UUID        PK
document_id   TEXT        INDEX
chunk_index   INT
content       TEXT
embedding     VECTOR(1024)  -- pgvector, HNSW index
kc_tags       TEXT[]        -- knowledge component etiketleri
metadata_     JSONB         -- {heading, source_type, ...}
created_at    TIMESTAMP
```

### `chat_history` — Etkileşim embedding deposu

```sql
id               UUID        PK
learner_id       UUID        INDEX
session_id       UUID
interaction_type TEXT        -- question|explanation_given|misconception|success|...
content_summary  TEXT
embedding        VECTOR(1024) -- pgvector, HNSW index
kc_tags          TEXT[]
correctness      BOOLEAN      -- KT sinyalinden (null olabilir)
created_at       TIMESTAMP
```

### `student_profiles` — Öğrenci profili

```sql
id                UUID   PK
display_name      TEXT
preferred_language TEXT   DEFAULT 'tr'
preferences       JSONB   -- öğrenme hızı, açıklama stili vb.
created_at        TIMESTAMP
updated_at        TIMESTAMP
```

### `mastery_scores` — KC seviyesinde bilgi durumu

```sql
learner_id       UUID   PK (composite)
kc_id            TEXT   PK (composite)
p_mastery        FLOAT  -- [0, 1] AKT/DKT çıktısı
attempts         INT
last_interaction TIMESTAMP
subject          TEXT   -- müfredat alanı
```

### `student_errors` — Kavram yanılgısı takibi

```sql
id          UUID   PK
learner_id  UUID
kc_id       TEXT
description TEXT
resolved    BOOLEAN DEFAULT false
detected_at TIMESTAMP
```

---

## 4. POST /chat — Tam İstek Akışı

```
İstemci: JWT + message gönderir
│
│  POST /chat
│  Authorization: Bearer <JWT>
│  { "session_id": <uuid|null>, "message": "Gradient descent nasıl çalışır?" }
│
▼
FastAPI → JWT → learner_id çıkar
│
▼
ChatOrchestrator.chat() başlar
│
├─ ADIM 1: Oturum Yükle / Oluştur
│   SessionManager.get_or_create(session_id, learner_id)
│   → Redis'ten yükle veya yeni SessionContext oluştur
│
├─ ADIM 2: Öğrenci Profilini Yükle
│   ProfileRetriever.get_or_create(learner_id)
│   → DB'den çek, yoksa oluştur
│
├─ ADIM 3: Paralel Geri Alma (asyncio.gather)
│   ├─ A) İçerik Geri Alma
│   │    ContentRetriever.retrieve(message)
│   │    → Sorguyu embed et → pgvector'da cosine distance ile ara
│   │    → Opsiyonel: LLM tabanlı yeniden sıralama
│   │    → Döndür: list[RetrievedChunk]
│   │
│   └─ B) Öğrenci Belleği Geri Alma
│        PgVectorStore.search_learner_memory(learner_id)
│        → Geçmiş etkileşimlerde semantik arama
│        → Döndür: list[InteractionEmbedding]
│
├─ ADIM 4: KC Çıkarımı + Mastery Tahmini
│   MasteryEstimator.estimate_for_query(message)
│   → KCMapper.extract() → LLM: "Bu sorgudaki KC'ler nelerdir?"
│   → DB'den KC mastery değerlerini yükle (tracer durumunu başlat)
│   → tracer.estimate(kc_ids)
│   → Döndür: (kc_ids, KCMasterySnapshot)
│
├─ ADIM 5: Çözülmemiş Kavram Yanılgılarını Getir
│   MisconceptionStore.get_unresolved(learner_id, kc_ids)
│   → Döndür: list[Misconception]
│
├─ ADIM 6: Pedagojik Strateji Seç
│   PedagogyPlanner.select_strategy(mastery_snapshot)
│   → Ortalama mastery hesapla
│   → Eşiğe göre strateji seç (reinforcement / practice / challenge)
│   → İlgili .md dosyasını oku
│
├─ ADIM 7: Prompt Oluştur
│   PromptBuilder.build(...)
│   Birleştirme sırası:
│   1. system_base.md içeriği
│   2. Pedagojik strateji direktifi
│   3. Öğrenci profil bağlamı
│   4. KC mastery anlık görüntüsü (görsel ilerleme çubukları)
│   5. Çözülmemiş kavram yanılgıları
│   6. Benzer geçmiş etkileşimler (bellek RAG)
│   7. İlgili müfredat chunk'ları (içerik RAG)
│   8. Konuşma geçmişi (son 6 tur)
│   9. Mevcut kullanıcı sorgusu
│   → Döndür: list[Message]
│
├─ ADIM 8: LLM Tamamlama
│   llm_client.complete(messages, temp=0.7, max_tokens=1024)
│   → OpenAI | Anthropic | Novita
│   → Döndür: LLMResponse
│
├─ ADIM 9: Oturum Durumunu Güncelle (Senkron)
│   → Tur ekle: user + message + kc_tags
│   → Tur ekle: assistant + response + kc_tags
│   → active_kc_ids + mastery_snapshot güncelle
│   → SessionManager.save() → Redis
│
├─ ADIM 10: Doğruluk Değerlendirmesi + Kavram Yanılgısı Tespiti (Paralel)
│   ├─ A) CorrectnessEvaluator.evaluate()
│   │    → LLM: Öğrencinin anlayışı doğru mu?
│   │    → Döndür: True | False | None
│   │
│   └─ B) MisconceptionDetector.detect()
│        → LLM: Öğrenci mesajındaki kavram yanılgıları neler?
│        → Döndür: list[(kc_id, description)]
│
├─ ADIM 11: Doğruluk Sinyali Varsa Mastery Güncelle
│   → Her kc_id için: tracer.update(learner_id, kc_id, correct)
│   → Döndür: {kc_id: yeni_p_mastery}
│
├─ ADIM 12: Arka Plan İşi Kuyruğa Al (Fire-and-Forget)
│   WorkerQueue.push({job}) → Redis LPUSH
│   job = {
│     learner_id, session_id, interaction_type,
│     content_summary, kc_tags, new_mastery,
│     subject, misconceptions
│   }
│
└─ ADIM 13: İstemciye Yanıt Dön
    HTTP 200 OK
    {
      "content": "...",
      "session_id": UUID,
      "kc_ids": ["gradient_descent", "optimization"],
      "mastery_snapshot": { "gradient_descent": 0.45, "optimization": 0.62 },
      "model": "meta-llama/llama-3.1-8b-instruct",
      "input_tokens": 842,
      "output_tokens": 187
    }
```

### Arka Plan Worker (Redis Kuyruğu)

```
[Ayrı süreç — isteği beklemez]

1. WorkerQueue.pop(timeout=5) → Redis BRPOP
2. İşi parse et → Interaction + misconceptions
3. MemoryUpdater.update():
   a) InteractionLogger.log(interaction)
      → Etkileşimi embed et → chat_history pgvector'a yaz
   b) Her kavram yanılgısı için:
      → MisconceptionStore.add() → student_errors
   c) Her KC için:
      → ProfileRetriever.upsert_kc_mastery() → mastery_scores
   d) session.commit()
4. Hata durumunda: 3 kez yeniden dene (2s/4s/8s), sonra DLQ'ya taşı
5. Döngü (sonsuz)
```

---

## 5. Chunklama Mantığı (Detaylı)

**Dosya:** [app/services/content_rag/chunker.py](app/services/content_rag/chunker.py)

```python
Chunker(max_chars=1500, overlap_chars=150).chunk(text) → list[TextChunk]
```

### Algoritma: Yapı-Farkındalıklı Bölme

**ADIM 1 — Markdown Başlıklarına Göre Böl (h1-h3)**

```
Regex: ^#{1,3}\s+(.+)$

Metin başlık gruplarına ayrılır:
  [("", intro paragraf), ("# Bölüm 1", içerik), ("## Alt Bölüm", içerik), ...]
Her (başlık, bölüm_içeriği) çifti bağımsız işlenir.
```

**ADIM 2 — Her Bölümü Karakter Limitine Göre Böl**

```
Eğer bölüm ≤ max_chars → tek chunk olarak tut

Eğer bölüm > max_chars:
  → Paragraflara böl (regex: \n\n+)
  → Paragrafları biriktir; eklemek max_chars'ı aşana kadar
  → Tek paragraf > max_chars ise:
     → Cümle sınırlarına göre böl (regex: (?<=[.!?])\s+)
```

**ADIM 3 — Örtüşme (Overlap) Uygula**

```
Her chunk (ilki hariç), önceki chunk'ın son overlap_chars karakterini başına ekler.
Amaç: Embedding kalitesi için bağlam sürekliliğini korumak.
```

### Örnek

```
Girdi metni (max_chars=500, overlap=50):
───────────────────────────────────────
# Bölüm 1

Bu çok uzun bir paragraftır...

Bu da uzun bir paragraftır...

## Alt Bölüm 1.1

Kısa bir paragraf.
───────────────────────────────────────

Çıktı chunk'ları:
[
  TextChunk(
    text="# Bölüm 1\n\nBu çok uzun bir paragraftır...",
    chunk_index=0,
    heading="Bölüm 1",
    char_start=0
  ),
  TextChunk(
    text="...paragraftır.\n\nBu da uzun bir paragraftır...",
    chunk_index=1,
    heading="Bölüm 1",
    char_start=250   # overlap ile önceki son 50 karakter dahil
  ),
  TextChunk(
    text="...paragraftır.\n\n## Alt Bölüm 1.1\n\nKısa bir paragraf.",
    chunk_index=2,
    heading="Alt Bölüm 1.1",
    char_start=490
  ),
]
```

---

## 6. RAG Pipeline (Veri Alımı → Geri Alma)

### 6.1 Ingestion Pipeline

**Dosya:** [app/services/content_rag/ingestion_pipeline.py](app/services/content_rag/ingestion_pipeline.py)

```
Kullanıcı belge yükler
│
├─ PDF ise: pypdf → her sayfadan metin çıkar → "\n\n" ile birleştir
│
├─ Metin ise: doğrudan kullan
│
▼
Chunker.chunk(text) → list[TextChunk]
│
▼
embedder.embed_batch(texts) → list[list[float]]  (1024 boyutlu vektörler)
│
▼
Her (chunk, embedding) çifti için:
  PgVectorStore.upsert_content_chunk(
    document_id, chunk_index, content,
    embedding, kc_tags, metadata={heading, source_type}
  )
│
▼
Döndür: IngestionResult(document_id, chunks_written, chars_total)
```

**Temel özellikler:**
- Metin ve PDF desteği
- `replace_existing=True` ise eski chunk'ları siler (DELETE önce)
- Verimlilik için batch embedding
- Metadata korunur (başlık, kaynak türü)
- KC etiketleri chunk'larla ilişkilendirilir

### 6.2 Retrieval (Geri Alma)

**Dosya:** [app/services/content_rag/retriever.py](app/services/content_rag/retriever.py)

```
Kullanıcı sorgusu: "Gradient descent nasıl çalışır?"
│
▼
1. embedder.embed(query) → 1024 boyutlu vektör
│
▼
2. PgVectorStore.search_content(
     query_embedding,
     top_k=5,
     kc_filter=ctx.active_kc_ids   # opsiyonel
   )
   
   SQL (pgvector):
   SELECT * FROM curriculum_chunks
   ORDER BY embedding <-> query_embedding   -- cosine mesafesi
   LIMIT 5
   [WHERE kc_tags && kc_filter]
│
▼
3. Opsiyonel: Reranker.rerank(query, chunks, top_k)
   → rerank_enabled=True ise aktif
   → LLM: "Her chunk'ı 0-10 arası puanla"
   → LLM puanlarına göre yeniden sırala
│
▼
Döndür: list[RetrievedChunk]
  {document_id, chunk_index, content, heading, kc_tags}
```

---

## 7. Knowledge Tracing (Bilgi Takibi)

### 7.1 KC Çıkarımı

**Dosya:** [app/services/knowledge_tracing/kc_mapper.py](app/services/knowledge_tracing/kc_mapper.py)

```
Sorgu: "Gradient descent nasıl çalışır?"
│
▼
LLM çağrısı (yapılandırılmış çıkarım):
  System: "Akademik kavramları (KC) tespit et"
  User:   "Metin: ..."
  Temperature: 0.0
│
▼
LLM çıktısı: ["gradient_descent", "optimization"]
│
▼
Doğrulama: küçük harf, alt çizgi ayraç, maks 4 kelime
│
▼
Döndür: list[str]
```

### 7.2 AKT Modeli (Attentive Knowledge Tracing)

**Dosya:** [app/services/knowledge_tracing/akt_model.py](app/services/knowledge_tracing/akt_model.py)

Ghosh et al. (2020) — Basitleştirilmiş uygulama.

**Öğrenci başına durum:**
```python
_state[learner_id][kc_id] = _KCState(
    p_mastery: float,        # mevcut mastery tahmini [0, 1]
    attempts: int,           # toplam gözlem sayısı
    weighted_correct: float, # sum(doğruluk × azalma_ağırlığı)
    weight_sum: float        # sum(azalma ağırlıkları)
)
```

**Tahmin:**
```
raw_accuracy = weighted_correct / weight_sum
confidence   = 1 - exp(-attempts / alpha)    # [0, 1]
p_mastery    = prior + confidence × (raw_accuracy - prior)
              → [0, 1] aralığında kırp
```

**Güncelleme (her etkileşimden sonra):**
```
1. Tarihi ağırlıklara monotonic azalma uygula:
   weighted_correct *= decay_factor  (varsayılan: 0.85)
   weight_sum       *= decay_factor

2. Yeni gözlem ekle:
   weighted_correct += 1.0 if correct else 0.0
   weight_sum       += 1.0
   attempts         += 1

3. Mastery'yi yeniden hesapla ve kaydet
```

**Temel fikir:** Son gözlemler daha yüksek ağırlık alır; güven deneme sayısıyla artar.

### 7.3 DKT Modeli (Deep Knowledge Tracing — Bayesian formülasyon)

**Dosya:** [app/services/knowledge_tracing/dkt_model.py](app/services/knowledge_tracing/dkt_model.py)

Piech et al. (2015) — BKT parametreleriyle uygulanmış.

**Parametreler:**
```
P_INIT   = 0.3    # ön bilgi (gözlem öncesi)
P_LEARN  = 0.15   # öğrenme geçişi: ~mastered → mastered (doğru cevapta)
P_FORGET = 0.05   # unutma geçişi: mastered → ~mastered (yanlış cevapta)
P_SLIP   = 0.1    # P(yanlış | mastered)
P_GUESS  = 0.2    # P(doğru | ~mastered)
```

**Bayesian güncelleme:**
```
Doğru cevap için:
  P(doğru | mastered)  = 1 - P_SLIP
  P(doğru | ~mastered) = P_GUESS

Yanlış cevap için:
  P(yanlış | mastered)  = P_SLIP
  P(yanlış | ~mastered) = 1 - P_GUESS

numerator   = P(gözlem | mastered) × p_mastery
denominator = numerator + P(gözlem | ~mastered) × (1 - p_mastery)
p_posterior = numerator / denominator

Öğrenme / unutma:
  if correct:
    p_new = p_posterior + (1 - p_posterior) × P_LEARN
  else:
    p_new = p_posterior × (1 - P_FORGET)

→ [0, 1] aralığında kırp
```

---

## 8. Pedagojik Stratejiler

**Dosya:** [app/services/orchestration/pedagogy_planner.py](app/services/orchestration/pedagogy_planner.py)

Ortalama KC mastery değerine göre üç strateji seçilir:

| Mastery | Eşik | Strateji | Dosya | Amaç |
|---------|------|----------|-------|------|
| < 0.4 | UNKNOWN / INTRODUCED | **Scaffold** | `reinforcement.md` | Temel anlayış inşa et, basit açıklamalar, kavram parçalara ayrılır |
| 0.4 – 0.7 | PRACTICING | **Guided Practice** | `practice.md` | Çözülmüş örnekler, rehberli problem çözme, ipuçları |
| ≥ 0.7 | MASTERED | **Challenge** | `challenge.md` | İleri düzey problemler, kavramları yeni alanlara transfer |

Tüm stratejiler **Sokratik yöntemi** uygular: sistem doğrudan cevap vermek yerine yönlendirici sorular sorar.

---

## 9. Oturum Yönetimi (Redis)

**Key formatı:** `session:{session_id}`

**Değer:** `SessionContext.to_dict()` JSON olarak serileştirilmiş.

```json
{
  "session_id": "uuid",
  "learner_id": "uuid",
  "turns": [
    {
      "role": "user",
      "content": "...",
      "kc_tags": ["gradient_descent"],
      "timestamp": "2026-04-15T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "...",
      "kc_tags": ["gradient_descent"],
      "timestamp": "2026-04-15T10:30:02Z"
    }
  ],
  "active_kc_ids": ["gradient_descent"],
  "mastery_snapshot": {
    "gradient_descent": {"p_mastery": 0.45, "attempts": 3}
  },
  "started_at": "2026-04-15T10:25:00Z",
  "last_activity": "2026-04-15T10:30:02Z"
}
```

**TTL:** `session_ttl_seconds` (varsayılan: 3600 saniye = 1 saat)

---

## 10. Kimlik Doğrulama ve Middleware

### JWT Doğrulama

**Dosya:** [app/api/dependencies_auth.py](app/api/dependencies_auth.py)

```
HTTPBearer() → HTTPAuthorizationCredentials
decode_token(token: str) → UUID:
  1. "." ile böl
  2. Payload'ı çıkar (index 1)
  3. Base64url decode et (padding ekle)
  4. JSON parse et
  5. "sub" alanını al → UUID'e dönüştür
```

Hata durumunda: `401 Unauthorized`

### CORS

```python
allow_origins = ["*"]
allow_methods = ["*"]
allow_headers = ["*"]
```

### DB Oturumu (Dependency Injection)

```
FastAPI Depends(get_session) → AsyncSession:
  async with _session_factory() as session:
    → Başarıda: commit
    → Hata durumunda: rollback + yeniden fırlat
```

---

## 11. Yapılandırma Hiyerarşisi

**Öncelik sırası (yüksekten düşüğe):**

1. Ortam değişkenleri (gizliler: API anahtarları, DB şifresi)
2. `config.json` (gizli olmayan ayarlar)
3. `Settings` sınıfındaki alan varsayılanları
4. `.env` dosyası (yedek)

**Temel ayarlar:**

```
LLM_PROVIDER              = openai | anthropic | novita
EMBEDDER_PROVIDER         = bge_m3 | openai | novita
KT_MODEL                  = akt | dkt
MASTERY_THRESHOLD_LOW     = 0.4
MASTERY_THRESHOLD_HIGH    = 0.7
CONTENT_TOP_K             = 5
MEMORY_TOP_K              = 3
RERANK_ENABLED            = false
```

---

## 12. API Endpoints

| Metod | Yol | Auth | Açıklama |
|-------|-----|------|---------|
| POST | `/auth/register` | — | Yeni öğrenci kaydı (Supabase) |
| POST | `/auth/login` | — | Giriş → JWT token |
| POST | `/chat` | JWT | Ana sohbet: mastery + RAG + pedagoji → LLM yanıtı |
| POST | `/ingest/text` | JWT | Metin al → chunk → embedding |
| POST | `/ingest/pdf` | JWT | PDF al → chunk → embedding |
| GET | `/profile/{learner_id}` | JWT | Öğrenci profili + konuya göre mastery |
| POST | `/session/reset` | JWT | Redis'ten oturumu temizle |
| GET | `/health` | — | Sağlık kontrolü |

---

## 13. Hata Yönetimi ve Dayanıklılık

**Yeniden deneme stratejileri:**
- **LLM çağrıları:** Tenacity (3 deneme, exponential backoff 2–10s)
- **Worker işleri:** 3 deneme (2s / 4s / 8s aralıklar), sonra DLQ

**Hata yanıtları:**

| Kod | Durum |
|-----|-------|
| 400 | Geçersiz girdi (örn. çok büyük PDF) |
| 401 | Geçersiz/süresi dolmuş JWT |
| 403 | Oturum yetki hatası |
| 422 | İşlenemeyen varlık (doğrulama hatası) |
| 5xx | Sunucu hataları; worker işi yeniden denenir |

**Loglama:**
- Tüm orchestration adımları loglanır (learner_id, session_id, kc_ids)
- LLM çağrıları token sayılarıyla loglanır
- Worker başarısızlıkları hata detaylarıyla loglanır

---

## 14. Genişletilebilirlik

**Plug-in bileşenler:**

| Bileşen | Nasıl Genişletilir |
|---------|-------------------|
| LLM sağlayıcılar | `BaseLLMClient` implement et + `build_llm_client()`'a ekle |
| Embedder'lar | `BaseEmbedder` implement et + `build_embedder()`'a ekle |
| Knowledge tracer | `BaseKnowledgeTracer` implement et + `build_tracer()`'a ekle |
| Pedagoji stratejileri | `prompts/` dizinine yeni `.md` dosyası ekle |
| Chunklama | `Chunker.__init__()` parametrelerini ayarla (max_chars, overlap_chars) |

**Kod değişikliği gerektirmeyen yapılandırma:**
- Yeniden sıralamayı etkinleştir/devre dışı bırak: `RERANK_ENABLED`
- Mastery eşiklerini ayarla: `MASTERY_THRESHOLD_LOW/HIGH`
- KT modelini değiştir: `KT_MODEL`
- Geri alma ayarları: `CONTENT_TOP_K`, `MEMORY_TOP_K`

---

## 15. Performans Karakteristikleri

**Gecikme (her /chat isteği için):**

| Bileşen | Tahmini Süre |
|---------|-------------|
| KC çıkarımı (LLM) | ~0.5–1s |
| İçerik geri alma (pgvector) | ~50–100ms |
| Bellek geri alma (pgvector) | ~50–100ms |
| Mastery tahmini (bellekte KT) | ~10–50ms |
| LLM tamamlama | ~1–5s |
| Oturum kaydetme (Redis) | ~10–20ms |
| **Toplam** | **~2–7s** (LLM gecikme baskındır) |

**Ölçeklenebilirlik:**
- Oturumlar: Redis in-memory; bellek limitine kadar milyonlarca oturum
- İçerik: PostgreSQL + pgvector; document_id index + embedding HNSW
- Worker: Tek süreç; yatay ölçekleme için daha fazla worker başlatılabilir

---

## 16. Bileşen Etkileşim Diyagramı

```
┌─────────────────────────────────────────────────────────────────────┐
│                          İSTEK KAPSAMI                              │
├─────────────────────────────────────────────────────────────────────┤
│  JWT → learner_id                                                   │
│  Redis → SessionContext                                             │
│  ┌─────────────────────────────┐                                    │
│  │  pgvector                   │    ← embed(query) → semantic ara   │
│  │  curriculum_chunks          │    → RetrievedChunk[]              │
│  │  chat_history               │    → InteractionEmbedding[]        │
│  └─────────────────────────────┘                                    │
│  LLM → KC ID çıkar → DB'den mastery yükle → AKT/DKT tahmin et     │
│  PedagogyPlanner → strateji seç → prompt oluştur                   │
│  LLM → yanıt üret                                                   │
│  Redis → oturumu güncelle                                           │
│  LLM → doğruluk + kavram yanılgısı (paralel)                       │
│  Redis Queue → arka plan işi kuyruğa al                             │
│  → İstemciye yanıt dön                                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     WORKER KAPSAMI (Async)                          │
├─────────────────────────────────────────────────────────────────────┤
│  Redis BRPOP → işi parse et                                         │
│  embed(interaction) → chat_history pgvector'a yaz                   │
│  student_errors'a kavram yanılgısı yaz                              │
│  mastery_scores'u upsert et                                         │
│  DB commit                                                           │
│  Hata → 3× yeniden dene → DLQ                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   INGEST KAPSAMI (Yönetici Görevi)                  │
├─────────────────────────────────────────────────────────────────────┤
│  Metin/PDF al → metin çıkar                                         │
│  Chunker → yapı-farkındalıklı bölme                                 │
│  embed_batch() → vektörler üret                                      │
│  curriculum_chunks'a yaz (pgvector)                                  │
│  → IngestionResult dön                                               │
└─────────────────────────────────────────────────────────────────────┘
```
