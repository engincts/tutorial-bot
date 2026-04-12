# Tutor Bot

Kişiselleştirilmiş AI tabanlı öğrenci asistanı. Öğrencinin bilgi seviyesini gerçek zamanlı izleyen, müfredat içeriğini RAG ile sorgulayan ve pedagojik strateji uygulayan adaptif öğrenme sistemi.

## Mimari

```
POST /chat  (JWT Bearer zorunlu)
    │
    ├─► KC Tespiti          (kc_mapper — LLM assisted)
    ├─► Mastery Hesaplama   (AKT / DKT — saf Python, PyTorch yok)
    ├─► İçerik Retrieval    (pgvector semantic search + opsiyonel rerank)
    ├─► Hafıza Retrieval    (geçmiş etkileşimler + yanılgılar)
    ├─► Pedagoji Planlaması (mastery threshold → prompt seçimi)
    ├─► Prompt İnşası       (context fusion)
    └─► LLM Yanıtı          (OpenAI / Anthropic / Novita)
         │
         └─► Redis Worker: etkileşim kayıt + mastery + misconception güncelleme
```

## Kimlik Doğrulama

Sistem Supabase Auth kullanır. `/chat`, `/ingest/*` ve `/profile/*` endpoint'leri JWT Bearer token gerektirir.

### Token Alma

```bash
# Kayıt
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ogrenci@example.com", "password": "sifre123"}'

# Giriş
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ogrenci@example.com", "password": "sifre123"}'
# → {"access_token": "eyJ...", "learner_id": "uuid"}
```

## Kurulum

### Gereksinimler

- Python 3.11+
- Docker & Docker Compose
- Supabase projesi (Auth için)

### Supabase Kurulumu

1. [supabase.com](https://supabase.com) üzerinde yeni proje oluştur
2. **Project Settings → API** sayfasından şunları kopyala:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_KEY`
3. **Project Settings → API → JWT Settings** sayfasından:
   - `JWT Secret` → `SUPABASE_JWT_SECRET`

### Hızlı Başlangıç

```bash
# 1. Ortam değişkenlerini ayarla
cp .env.example .env          # Linux/Mac
copy .env.example .env        # Windows
# .env dosyasını düzenle — LLM_PROVIDER, API key ve Supabase bilgilerini gir

# 2. Servisleri ayağa kaldır (PostgreSQL + pgvector, Redis, worker)
docker compose up -d --build

# 3. Veritabanı migrasyonlarını uygula
alembic upgrade head

# 4. Örnek müfredat yükle (token ile)
python scripts/seed_curriculum.py
```

> **Not (Linux/Mac):** `make` kuruluysa `make docker-up`, `make migrate`, `make dev` kullanılabilir.

### Manuel Kurulum (Docker olmadan)

```bash
python -m venv env
source env/bin/activate          # Linux/Mac
env\Scripts\activate             # Windows

pip install -e ".[dev]"

# PostgreSQL ve Redis'i lokal olarak başlat, sonra:
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker'ı ayrı terminal'de başlat
python -m app.worker.post_response_worker
```

## Konfigürasyon

Tüm ayarlar `.env` dosyasından okunur. Detaylı açıklamalar için `.env.example` dosyasına bakın.

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `LLM_PROVIDER` | `openai` \| `anthropic` \| `novita` | `novita` |
| `EMBEDDER_PROVIDER` | `openai` \| `novita` | `novita` |
| `KT_MODEL` | `akt` \| `dkt` | `dkt` |
| `RERANK_ENABLED` | LLM tabanlı chunk reranking | `false` |
| `MASTERY_THRESHOLD_LOW` | Bu seviyenin altı → scaffold modu | `0.4` |
| `MASTERY_THRESHOLD_HIGH` | Bu seviyenin üstü → challenge modu | `0.7` |
| `CONTENT_TOP_K` | Semantic search'ten kaç chunk çekilsin | `5` |

## API

Geliştirme ortamında Swagger UI: `http://localhost:8000/docs`

Swagger UI'da sağ üstteki **Authorize** butonuna token girerek endpoint'leri test edebilirsiniz.

### Endpoint'ler

| Method | Path | Auth | Açıklama |
|---|---|---|---|
| `POST` | `/auth/register` | — | Yeni öğrenci kaydı |
| `POST` | `/auth/login` | — | Giriş yap, token al |
| `POST` | `/chat` | JWT | Öğrenci mesajı gönder, pedagojik yanıt al |
| `POST` | `/ingest/text` | JWT | Metin içeriği müfredata ekle |
| `POST` | `/ingest/pdf` | JWT | PDF dökümanı müfredata ekle |
| `GET` | `/profile/{learner_id}` | JWT | Öğrenci profilini ve mastery snapshot'ını getir |
| `POST` | `/session/reset` | JWT | Aktif oturumu sıfırla |
| `GET` | `/health` | — | Servis sağlık kontrolü |

### Örnek İstek

```bash
# Önce login ol
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ogrenci@example.com", "password": "sifre123"}' \
  | jq -r '.access_token')

# Chat isteği gönder
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "learner_id": "550e8400-e29b-41d4-a716-446655440000",
    "session_id": "660e8400-e29b-41d4-a716-446655440001",
    "message": "Gradient descent nasıl çalışır?"
  }'
```

```json
{
  "content": "Önce şunu düşün: bir kayıp fonksiyonunun minimumunu bulmak istiyorsun...",
  "session_id": "660e8400-e29b-41d4-a716-446655440001",
  "kc_ids": ["gradient_descent", "optimization"],
  "mastery_snapshot": {
    "gradient_descent": 0.35,
    "optimization": 0.61
  },
  "model": "meta-llama/llama-3.1-8b-instruct",
  "input_tokens": 842,
  "output_tokens": 187
}
```

## Pedagoji Stratejileri

| Mastery | Strateji | Prompt |
|---|---|---|
| < 0.4 | Scaffold — temel kavramları yeniden kur | `prompts/reinforcement.md` |
| 0.4 – 0.7 | Guided Practice — yönlendirmeli alıştırma | `prompts/practice.md` |
| ≥ 0.7 | Challenge — ileri sorular ve transferler | `prompts/challenge.md` |

Tüm stratejilerde Sokratik yöntem zorunludur — sistem doğrudan cevap vermez.

## Müfredat Yükleme

```bash
TOKEN=eyJ...

# Metin olarak
curl -X POST http://localhost:8000/ingest/text \
  -H "Authorization: Bearer $TOKEN" \
  -F "document_id=backprop_intro" \
  -F "kc_tags=backpropagation,chain_rule" \
  -F "text=Geri yayılım algoritması..."

# PDF olarak
curl -X POST http://localhost:8000/ingest/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -F "document_id=lecture_3" \
  -F "kc_tags=neural_networks,activation_functions" \
  -F "file=@lecture3.pdf"
```

## Geliştirme

```bash
# Testleri çalıştır
APP_ENV=test OPENAI_API_KEY=sk-test python -m pytest tests/unit/ -v

# Lint
ruff check app/ tests/

# Yeni migration oluştur
alembic revision --autogenerate -m "migration_adi"
alembic upgrade head
```

## Proje Yapısı

```
tutor-bot/
├── app/
│   ├── api/routes/         # FastAPI endpoint'leri
│   ├── domain/             # Core data modeller
│   ├── services/
│   │   ├── orchestration/  # Chat akış yönetimi
│   │   ├── content_rag/    # Döküman ingestion + retrieval
│   │   ├── learner_memory/ # Öğrenci hafızası CRUD
│   │   └── knowledge_tracing/ # AKT/DKT mastery tahmini
│   ├── infrastructure/     # DB, Redis, LLM, embedder adaptörleri
│   └── worker/             # Async post-response işlemleri
├── migrations/             # Alembic schema versiyonları
├── prompts/                # Pedagoji prompt şablonları
├── scripts/                # Seed ve eval araçları
└── tests/
    ├── unit/
    └── integration/
```

## Tech Stack

- **API**: FastAPI + Uvicorn (async)
- **Auth**: Supabase Auth (JWT / JWKS doğrulama)
- **LLM**: OpenAI / Anthropic / Novita (env ile seçilebilir)
- **Embedding**: Novita BGE-M3 veya OpenAI (cloud-only, torch yok)
- **Vector Store**: PostgreSQL 16 + pgvector (HNSW index)
- **Session Cache**: Redis 7
- **Worker Queue**: Redis LPUSH/BRPOP
- **Knowledge Tracing**: AKT / DKT (saf Python)
- **ORM**: SQLAlchemy 2.0 async
