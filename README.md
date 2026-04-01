# Tutor Bot

Kişiselleştirilmiş AI tabanlı öğrenci asistanı. Öğrencinin bilgi seviyesini gerçek zamanlı izleyen, müfredat içeriğini RAG ile sorgulayan ve pedagojik strateji uygulayan adaptif öğrenme sistemi.

## Mimari

```
POST /chat
    │
    ├─► KC Tespiti          (kc_mapper — LLM assisted)
    ├─► Mastery Hesaplama   (AKT / DKT — PyTorch)
    ├─► İçerik Retrieval    (pgvector semantic search)
    ├─► Hafıza Retrieval    (geçmiş etkileşimler + yanılgılar)
    ├─► Pedagoji Planlaması (mastery threshold → prompt seçimi)
    ├─► Prompt İnşası       (context fusion)
    └─► LLM Yanıtı          (GPT-4o / Claude Sonnet)
         │
         └─► Async Worker: etkileşim kayıt + mastery güncelleme
```

## Kurulum

### Gereksinimler

- Python 3.11+
- Docker & Docker Compose
- AKT model checkpoint (`checkpoints/akt_assistments.pt`)

### Hızlı Başlangıç

```bash
# 1. Ortam değişkenlerini ayarla
cp .env.example .env          # Linux/Mac
copy .env.example .env        # Windows
# .env dosyasını düzenle — en azından OPENAI_API_KEY veya ANTHROPIC_API_KEY

# 2. Servisleri ayağa kaldır (PostgreSQL + pgvector, Redis)
docker compose up -d --build

# 3. Veritabanı migrasyonlarını uygula
alembic upgrade head

# 4. Örnek müfredat yükle
python scripts/seed_curriculum.py

# 5. API'yi başlat
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Not (Linux/Mac):** `make` kuruluysa yukarıdaki komutlar yerine `make docker-up`, `make migrate`, `make dev` kullanılabilir.

### Manuel Kurulum (Docker olmadan)

```bash
python -m venv env
source env/bin/activate          # Linux/Mac
env\Scripts\activate             # Windows

pip install -r requirements.txt

# PostgreSQL ve Redis'i lokal olarak başlat, sonra:
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Konfigürasyon

Tüm ayarlar `.env` dosyasından okunur. Detaylı açıklamalar için `.env.example` dosyasına bakın.

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `LLM_PROVIDER` | `openai` veya `anthropic` | `openai` |
| `EMBEDDER_PROVIDER` | `bge_m3` (local) veya `openai` | `bge_m3` |
| `KT_MODEL` | `akt` veya `dkt` | `akt` |
| `MASTERY_THRESHOLD_LOW` | Bu seviyenin altı → scaffold modu | `0.4` |
| `MASTERY_THRESHOLD_HIGH` | Bu seviyenin üstü → challenge modu | `0.7` |
| `CONTENT_TOP_K` | Semantic search'ten kaç chunk çekilsin | `5` |
| `RERANK_ENABLED` | Cross-encoder rerank aktif mi | `false` |

## API

Geliştirme ortamında Swagger UI: `http://localhost:8000/docs`

### Temel Endpoint'ler

| Method | Path | Açıklama |
|---|---|---|
| `POST` | `/chat` | Öğrenci mesajı gönder, pedagojik yanıt al |
| `POST` | `/ingest/text` | Metin içeriği müfredata ekle |
| `POST` | `/ingest/pdf` | PDF dökümanı müfredata ekle |
| `GET` | `/profile/{learner_id}` | Öğrenci profilini ve mastery snapshot'ını getir |
| `POST` | `/session/reset` | Aktif oturumu sıfırla |
| `GET` | `/health` | Servis sağlık kontrolü |

### Örnek İstek

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "learner_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Gradient descent nasıl çalışır?"
  }'
```

```json
{
  "content": "Önce şunu düşün: bir kayıp fonksiyonunun minimumunu bulmak istiyorsun...",
  "session_id": "...",
  "kc_ids": ["gradient_descent", "optimization"],
  "mastery_snapshot": {
    "gradient_descent": 0.35,
    "optimization": 0.61
  },
  "model": "gpt-4o",
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
# Metin olarak
curl -X POST http://localhost:8000/ingest/text \
  -F "document_id=backprop_intro" \
  -F "kc_tags=backpropagation,chain_rule" \
  -F "text=Geri yayılım algoritması..."

# PDF olarak
curl -X POST http://localhost:8000/ingest/pdf \
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
- **LLM**: GPT-4o veya Claude Sonnet (env ile seçilebilir)
- **Embedding**: BGE-M3 (local, Türkçe güçlü) veya OpenAI
- **Vector Store**: PostgreSQL 16 + pgvector (HNSW index)
- **Session Cache**: Redis 7
- **Knowledge Tracing**: AKT / DKT (PyTorch)
- **ORM**: SQLAlchemy 2.0 async
