# Tutor Bot

Kişiselleştirilmiş AI tabanlı öğrenci asistanı. Öğrencinin bilgi seviyesini gerçek zamanlı izleyen, müfredat içeriğini RAG ile sorgulayan ve pedagojik strateji uygulayan adaptif öğrenme sistemi.

## Öne Çıkan Özellikler

- **Adaptif Öğrenme**: BKT (Bayesian Knowledge Tracing) modeli ile öğrencinin her konu için hakimiyet seviyesini (mastery) kademeli olarak izler.
- **Hybrid Retrieval (RRF)**: Semantik (pgvector) ve anahtar kelime (pg_trgm) aramayı birleştirerek en doğru içeriği getirir.
- **Hallucination Monitoring**: LLM yanıtlarını kaynak dokümanlarla kıyaslayarak uydurma skorunu hesaplar.
- **SSE Streaming**: Yanıtları gerçek zamanlı (token-token) akıtır.
- **Question Bank Quiz**: PDF test kitaplarından Vision LLM ile soru çıkarıp öğrenciye ders bazlı quiz sunar.
- **Öğrenci Profili**: Çalışılan konuları ders bazında gruplar, hakimiyet yüzdesi ve radar grafiği gösterir.
- **Production-Ready**: Rate limiting, structured logging, request tracing ve Prometheus metrikleri.
- **Admin Panel**: Öğrenci ilerlemesi, uydurma logları ve sistem sağlığı için dashboard.

## Mimari Akış

```
Öğrenci → FastAPI → Redis Rate Limiter → Chat Orchestrator
                                              ├── KC Mapper (konu tespiti)
                                              ├── Hybrid RAG (müfredat)
                                              ├── Learner Memory (geçmiş)
                                              └── Mastery Estimator (BKT)
                                         → Pedagogy Planner
                                         → Prompt Builder
                                         → LLM (Novita)
                                         → SSE Stream → Öğrenci
                                         → Redis Worker (background)
                                              ├── Knowledge Tracing Update
                                              ├── Hallucination Check
                                              └── Memory Reflection
```

## Kurulum

### Gereksinimler

- Python 3.11+
- Docker & Docker Compose (opsiyonel)
- Supabase projesi

### Hızlı Başlangıç

```bash
# 1. Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenle

# 2. Virtual environment & bağımlılıklar
python -m venv env
env\Scripts\activate       # Windows
source env/bin/activate    # Linux/macOS
pip install -r requirements.txt

# 3. Veritabanı migrasyonları
alembic upgrade head

# 4. Backend başlat
uvicorn app.main:app --reload

# 5. Frontend başlat (ayrı terminal)
cd frontend && npm install && npm run dev
```

### Docker ile

```bash
docker compose up -d --build
alembic upgrade head
```

### Yönetici Erişimi

Admin paneline erişmek için `.env` dosyasındaki `ADMIN_EMAIL` ile giriş yapın. İlk girişte Supabase Auth üzerinden kayıt olmanız yeterlidir.

## Soru Bankası Yönetimi

TYT/AYT PDF test kitaplarından soruları Vision LLM ile otomatik çıkarıp `question_bank` tablosuna ekler.

```bash
# Tek PDF
python scripts/ingest_question_bank.py --pdf dosya.pdf --kc-id tyt_biyoloji

# Klasördeki tüm PDF'ler
python scripts/ingest_question_bank.py --folder pdfs/

# Bazı PDF'leri atla (zaten işlendiyse)
python scripts/ingest_question_bank.py --folder pdfs/ --skip tyt_biyoloji.pdf tyt_cografya.pdf
```

Script arka planda çalıştırmak için:

```powershell
Start-Job -ScriptBlock {
    Set-Location "C:\...\tutor-bot"
    env\Scripts\python scripts\ingest_question_bank.py --folder pdfs\
}
```

- Vision modeli: `qwen/qwen3-vl-235b-a22b-instruct` (Novita AI)
- Deterministic UUID: aynı soru tekrar eklenmez (`ON CONFLICT DO NOTHING`)
- Retry: 3 deneme, exponential backoff

## API Endpoint'leri

| Grup | Method | Path | Açıklama |
|---|---|---|---|
| **Auth** | `POST` | `/auth/login` | Giriş, JWT döner |
| **Auth** | `POST` | `/auth/register` | Kayıt |
| **Chat** | `POST` | `/chat/stream` | SSE gerçek zamanlı yanıt |
| **Quiz** | `GET` | `/quiz/subjects` | Kullanıcının çalıştığı dersler |
| **Quiz** | `GET` | `/quiz/bank-quiz?kc_id=...` | Soru bankasından quiz al |
| **Quiz** | `POST` | `/quiz/bank-answer` | Cevabı kontrol et, mastery güncelle |
| **Quiz** | `POST` | `/quiz/generate-adaptive` | Mastery'e göre uyarlamalı soru üret |
| **Profile** | `GET` | `/profile/{id}` | Öğrenci profili ve mastery tablosu |
| **Profile** | `DELETE` | `/profile/{id}` | Tüm verilerini sil (GDPR) |
| **Admin** | `GET` | `/admin/stats` | Sistem istatistikleri |
| **Admin** | `GET` | `/admin/hallucination-logs` | Uydurma logları |
| **Admin** | `GET` | `/admin/learners` | Öğrenci listesi |
| **Export** | `GET` | `/export/mastery/{id}/csv` | Mastery CSV |
| **Upload** | `POST` | `/upload` | PDF/Docx döküman yükle (RAG) |
| **Ops** | `GET` | `/health` | DB, Redis, DLQ sağlık kontrolü |
| **Ops** | `GET` | `/metrics` | Prometheus metrikleri |

Swagger UI: `http://localhost:8000/docs`

## İzleme ve Gözlemlenebilirlik

- **Prometheus Metrikleri**: `/metrics` üzerinden request latency, token kullanımı ve kuyruk derinliği.
- **Structured Logging**: Production ortamında ELK/Loki uyumlu JSON loglar.
- **Request Tracing**: Her isteğe atanan `X-Request-ID` ile korelasyon.
- **Health Probes**: `/healthz` (liveness) ve `/readyz` (readiness).

## Güvenlik

- **Supabase JWT**: Tüm korumalı endpoint'lerde token doğrulaması.
- **Rate Limiting**: Redis tabanlı istek sınırlama (Chat: 60/dk, Login: 10/dk).
- **GDPR/KVKK**: `/profile/{id}` DELETE ile tüm kullanıcı verileri (Auth + DB) silinir.

## Geliştirme ve Test

```bash
# Testler
pytest tests/ -v

# Değerlendirme scriptleri
python scripts/eval_retrieval.py
python scripts/eval_kt.py
python scripts/eval_hallucination.py
```
