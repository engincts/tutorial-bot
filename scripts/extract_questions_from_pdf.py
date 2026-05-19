"""
Test kitaplarındaki (PDF) soruları ve cevap anahtarlarını LLM kullanarak
otomatik ayıklayan ve question_bank tablosuna gömen yardımcı script.
"""
import asyncio
import uuid
import sys
import os
import json
import fitz  # PyMuPDF

# App dizinini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory
from app.infrastructure.llm import get_llm_client, Message
from sqlalchemy import text

async def extract_questions(pdf_path: str, kc_id: str, answer_key_text: str = None):
    if not os.path.exists(pdf_path):
        print(f"Hata: Belirtilen PDF dosyası bulunamadı -> {pdf_path}")
        return

    print(f"'{pdf_path}' yükleniyor...")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"PDF başarıyla yüklendi. Toplam sayfa sayısı: {total_pages}")

    # Sayfaların metinlerini topla
    pages_text = []
    for i in range(total_pages):
        page_text = doc[i].get_text()
        pages_text.append((i + 1, page_text))

    # Cevap anahtarını tespit etmeye çalış
    if not answer_key_text:
        print("Cevap anahtarı aranıyor...")
        last_pages_text = ""
        # Genellikle cevap anahtarları son 3 sayfada olur
        for i in range(max(0, total_pages - 3), total_pages):
            last_pages_text += pages_text[i][1]

        lower_text = last_pages_text.lower()
        if "cevap" in lower_text or "anahtar" in lower_text or "key" in lower_text:
            print("Son sayfalarda cevap anahtarı tespit edildi! Referans olarak kullanılacak.")
            answer_key_text = last_pages_text
        else:
            print("Cevap anahtarı son sayfalarda net bulunamadı. LLM'in mantıksal tahminlerine güvenilecek.")

    # Altyapıyı ilklendir
    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()
    llm = get_llm_client()

    print("İşlem başlatılıyor (Sayfalar 3'erli gruplar halinde işlenecektir)...")
    chunk_size = 3
    inserted_count = 0

    for idx in range(0, total_pages, chunk_size):
        chunk_pages = pages_text[idx:idx + chunk_size]
        chunk_content = ""
        for page_num, text_content in chunk_pages:
            # Cevap anahtarının olduğu bariz sayfaları soru çıkarma adımında atla
            if page_num > total_pages - 2 and ("cevap anahtarı" in text_content.lower() or "yanıt anahtarı" in text_content.lower()):
                continue
            chunk_content += f"\n--- SAYFA {page_num} ---\n{text_content}"

        if not chunk_content.strip():
            continue

        print(f"Sayfa {chunk_pages[0][0]} - {chunk_pages[-1][0]} işleniyor...")

        prompt = f"""
Sana bir test kitabından (PDF) çıkarılmış sayfalar ve varsa cevap anahtarı veriliyor.
Görevin, bu sayfalardaki çoktan seçmeli soruları tam metinleriyle tespit etmek, şıklarını ayıklamak ve cevap anahtarını kullanarak her sorunun doğru şıkkını bulmaktır.

Cevap Anahtarı / Doğru Cevap Referansı:
\"\"\"
{answer_key_text or "Cevap anahtarı bulunamadı, soruların kendi akışından ve mantığından doğru cevabı sen tespit et."}
\"\"\"

Soru Sayfaları Metin İçeriği:
\"\"\"
{chunk_content}
\"\"\"

ÇIKTI FORMATI:
Sadece geçerli bir JSON array döndürmelisin. Markdown veya ek hiçbir açıklama yazma. JSON formatı birebir şu şekilde olmalıdır:
[
  {{
    "question_text": "Sorunun tam metni (soru kökü dahil)...",
    "options": ["A) Şık Metni", "B) Şık Metni", "C) Şık Metni", "D) Şık Metni"],
    "correct_answer": "Doğru şıkkın tam metni (örneğin seçeneklerden biriyle karakteri karakterine aynı olmalı: 'A) Şık Metni')",
    "explanation": "Sorunun neden o şık olduğunun kısa açıklaması (opsiyonel)",
    "difficulty": "easy" | "medium" | "hard"
  }}
]
"""

        messages = [
            Message(role="system", content="Sen profesyonel bir eğitim materyali işleme asistanısın. Verilen test sayfalarından soruları eksiksiz ayıklayıp sadece JSON döndürürsün."),
            Message(role="user", content=prompt)
        ]

        try:
            response = await llm.complete(messages, temperature=0.1, max_tokens=3000)
            content = response.content.strip()

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            questions = json.loads(content)
            if not isinstance(questions, list):
                print("Hata: LLM geçerli bir liste döndürmedi.")
                continue

            async with session_factory() as session:
                for q in questions:
                    q_text = q.get("question_text")
                    options = q.get("options", [])
                    correct = q.get("correct_answer")
                    if not (q_text and options and correct):
                        continue

                    qid = uuid.uuid4()
                    await session.execute(
                        text("""
                            INSERT INTO question_bank (id, kc_id, question_text, options, correct_answer, explanation, difficulty)
                            VALUES (:id, :kc_id, :question, :options, :correct, :exp, :diff)
                        """).bindparams(
                            id=qid,
                            kc_id=kc_id,
                            question=q_text,
                            options=json.dumps(options, ensure_ascii=False),
                            correct=correct,
                            exp=q.get("explanation", ""),
                            diff=q.get("difficulty", "medium")
                        )
                    )
                    inserted_count += 1
                await session.commit()
                print(f"-> {len(questions)} adet soru başarıyla yüklendi.")

        except Exception as e:
            print(f"Bu grupta hata oluştu: {e}")

    print(f"\nİşlem Başarıyla Tamamlandı! Toplam {inserted_count} soru '{kc_id}' kazanımına eklendi.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Kullanım: python scripts/extract_questions_from_pdf.py <pdf_dosya_yolu> <kc_id> [opsiyonel_cevap_anahtarı_metni]")
        sys.exit(1)

    pdf = sys.argv[1]
    kc = sys.argv[2]
    ans = sys.argv[3] if len(sys.argv) > 3 else None

    asyncio.run(extract_questions(pdf, kc, ans))
