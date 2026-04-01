# Tutor Bot — Sistem Mimarisi

## Genel Bakis

Tutor Bot, her ogrencinin bilgi seviyesini takip eden, gecmisini hatirlayan ve pedagojik strateji uygulayan bir AI ogrenme asistanidir.

Bir ogrenci soru gonderdiginde sistem su adimlari izler:

```
Ogrenci mesaji
    |
    +-- 1. Kimlik dogrulama (JWT)
    |
    +-- 2. Session yukle (Redis)
    |
    +-- 3. Paralel veri cekme:
    |       +-- Mufredat araması (curriculum_chunks)
    |       +-- Gecmis sohbet araması (chat_history)
    |
    +-- 4. Konu tespiti (KC Mapper)
    |
    +-- 5. Bilgi seviyesi hesapla (Mastery Estimator)
    |
    +-- 6. Yanilgilari kontrol et (student_errors)
    |
    +-- 7. Pedagoji stratejisi sec
    |
    +-- 8. Prompt olustur
    |
    +-- 9. LLM'e gonder → yanit al
    |
    +-- 10. Session guncelle (Redis)
    |
    +-- 11. Arka planda: chat_history'e kaydet
```

---

## Veritabani Tablolari

### `users`
Kim oldugunu bildigimiz tablo. Kayit ve giris islemleri burada.

| Kolon | Aciklama |
|---|---|
| `id` | Kullanici kimlik numarasi |
| `email` | Giris icin email |
| `hashed_password` | Sifrelenmiş parola (bcrypt) |
| `learner_id` | Bu kullanicinin ogrenci profiliyle baglantisi |
| `created_at` | Kayit tarihi |

---

### `student_profiles`
Ogrenciye ait temel bilgiler.

| Kolon | Aciklama |
|---|---|
| `id` | Ogrenci kimlik numarasi (`learner_id` ile eslesir) |
| `display_name` | Gorunen ad |
| `preferred_language` | Tercih edilen dil (varsayilan: tr) |
| `preferences` | JSON formatinda ozel tercihler |

---

### `mastery_scores`
Her ogrencinin her konu (Knowledge Component) icin bilgi seviyesi.

| Kolon | Aciklama |
|---|---|
| `learner_id` | Ogrenci |
| `kc_id` | Konu kodu (ornegin: `gradient_descent`) |
| `p_mastery` | 0.0–1.0 arasi bilme olasiligi |
| `attempts` | O konuya kac kez girildi |
| `last_interaction` | Son etkilesim zamani |

Sistem bu skoru kullanarak pedagoji stratejisi secer (bkz. Pedagoji bolumu).

---

### `student_errors`
Ogrencide tespit edilen yanilgilar.

| Kolon | Aciklama |
|---|---|
| `learner_id` | Ogrenci |
| `kc_id` | Hangi konuyla ilgili |
| `description` | Yanilginin aciklamasi |
| `resolved` | Duzeltildi mi? |

Her sohbette cozulmemis yanilgilar prompt'a eklenir, sistem bu yanilgilari dikkate alarak yanit verir.

---

### `chat_history`
Ogrencinin tum sohbet gecmisi — vektorel olarak depolanir.

| Kolon | Aciklama |
|---|---|
| `learner_id` | Ogrenci |
| `session_id` | Hangi oturumdan |
| `interaction_type` | `question` / `misconception` / `success` / `struggle` |
| `content_summary` | Mesajin ozeti (max 300 karakter) |
| `embedding` | Mesajin vektorel temsili (1024 boyut) |
| `kc_tags` | Ilgili konu kodlari |

Yeni bir soru geldiginde bu tabloda **semantik arama** yapilir: en alakali 3 gecmis etkilesim bulunur ve context'e eklenir.

---

### `curriculum_chunks`
Sisteme yuklenen ders iceriginin parca parca saklandigi tablo.

| Kolon | Aciklama |
|---|---|
| `document_id` | Hangi belgeden geldi |
| `chunk_index` | Belge icindeki sira numarasi |
| `content` | Metin icerigi |
| `embedding` | Vektorel temsil |
| `kc_tags` | Bu parcayla ilgili konu kodlari |

Ogrenci soru sordigunda bu tabloda semantik arama yapilir: en alakali 5 mufredat parcasi bulunur ve context'e eklenir.

---

## Retrieval (Veri Cekme)

Her `/chat` isteğinde iki farkli kaynaktan paralel arama yapilir:

```
Ogrenci sorusu → Embedding (Novita bge-m3)
                      |
         +------------+------------+
         |                         |
   curriculum_chunks          chat_history
   (mufredat araması)      (kisisel hafiza)
   top_k = 5               top_k = 3
         |                         |
         +------------+------------+
                      |
              Context'e eklenir
```

**`content_top_k = 5`**: Mufredat tablosundan cosine similarity ile en yakin 5 parca.
**`memory_top_k = 3`**: Ogrencinin gecmis sohbetlerinden en yakin 3 etkilesim. Bu arama `learner_id` ile izole — baska ogrencinin gecmisi karisimaz.

---

## Pedagoji Stratejisi

Sistem her sohbette ogrencinin o konudaki mastery skoruna gore strateji secer:

```
mastery_scores tablosundaki p_mastery degeri
         |
    < 0.4 -----> SCAFFOLD
                 Temel kavrami yeniden anlat.
                 Adim adim yonlendir.
                 Sokratik sorularla temeli olustur.

  0.4–0.7 -----> GUIDED PRACTICE
                 Alıştırma yaptir.
                 Ipuclari ver ama cevabi verme.
                 Hatalarda kibarca duzelt.

    >= 0.7 -----> CHALLENGE
                 Ileri duzey soru sor.
                 Transfer problemleri ver.
                 Baglamlari genislet.
```

Her strateji `prompts/` klasoründeki farkli prompt sablonuna karsilik gelir.

---

## Kimlik Dogrulama (Auth)

```
POST /auth/register
    email + sifre → learner_id olusturulur → JWT token doner

POST /auth/login
    email + sifre → veritabanindaki learner_id bulunur → JWT token doner

POST /chat
    Authorization: Bearer <token>
    → token'dan learner_id cikartilir
    → o ogrenciye ait tum hafiza ve mastery yuklenir
```

JWT suresi: 7 gun (config.json'da degistirilebilir).
Kullanici cikis yapip tekrar giris yapsa bile ayni `learner_id` ile eslestigi icin hafizasi ve bilgi seviyesi korunur.

---

## Session (Aktif Konusma)

Aktif konusma Redis'te saklanir (TTL: 1 saat).

```
Redis key: session:{session_id}
Icerik: son 6 mesajin konusma gecmisi + aktif konu kodlari + anlık mastery snapshot
```

Session expire olunca Redis'ten silinir. Kalici kayit chat_history tablosundadir.

---

## Konfigurasyon

Tum ayarlar iki yerden okunur:

| Dosya | Ne icerir |
|---|---|
| `config.json` | Secret olmayan ayarlar (model, esikler, top_k, JWT suresi) |
| `.env` | Sadece secret'lar (API keyleri, DB sifresi, JWT secret) |

Oncelik sirasi: ortam degiskenleri > `config.json` > `.env` > varsayilanlar.

---

## Tech Stack

| Katman | Teknoloji |
|---|---|
| API | FastAPI + Uvicorn (async) |
| LLM | Novita (meta-llama/llama-3.1-8b-instruct) |
| Embedding | Novita (baai/bge-m3, 1024 boyut) |
| Vector Store | PostgreSQL 16 + pgvector (HNSW index) |
| Session Cache | Redis 7 (TTL 1 saat) |
| Knowledge Tracing | AKT/DKT (PyTorch, heuristic mod) |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| ORM | SQLAlchemy 2.0 async |
| Migration | Alembic |
