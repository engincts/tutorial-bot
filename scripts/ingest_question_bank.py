"""
TYT/AYT PDF test kitaplarından Vision LLM ile soru çıkar, question_bank'a ekle.
OCR gerektirmez — sayfaları doğrudan görüntü olarak LLM'e gönderir.
Novita'nın vision modelini kullanır (OpenAI uyumlu API).

Kurulum:
  pip install openai pymupdf

Kullanım:
  python scripts/ingest_question_bank.py --pdf dosya.pdf --kc-id tyt_biyoloji
  python scripts/ingest_question_bank.py --folder klasor/ --kc-id tyt_karisik
"""

import asyncio
import argparse
import base64
import json
import re
import sys
import os
from pathlib import Path
from uuid import uuid5, UUID

import fitz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AsyncOpenAI
from app.infrastructure.database import init_db, get_session_factory
from app.settings import get_settings
from sqlalchemy import text as sa_text

NOVITA_BASE_URL = "https://api.novita.ai/v3/openai"
VISION_MODEL = "qwen/qwen3-vl-235b-a22b-instruct"
PAGES_PER_CHUNK = 2
DPI = 150
_NS = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")  # sabit namespace — deterministik id için

def _question_id(kc_id: str, question_text: str) -> UUID:
    """Aynı soru her zaman aynı UUID'yi üretir → ON CONFLICT DO NOTHING gerçekten çalışır."""
    return uuid5(_NS, f"{kc_id}::{question_text}")


# ── PDF araçları ──────────────────────────────────────────────


def page_to_jpeg(page, dpi: int = DPI) -> bytes:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("jpeg")


def find_answer_key_indices(doc) -> list[int]:
    """Son 15 sayfada 'cevap anahtarı' içerenleri döndürür; bulamazsa son 3 sayfayı döndürür."""
    n = len(doc)
    found = []
    for i in range(max(0, n - 15), n):
        text = doc[i].get_text().lower()
        if any(w in text for w in ("cevap anahtarı", "cevap anahtar", "yanıt anahtar")):
            found.append(i)
    return found if found else list(range(max(0, n - 3), n))


# ── LLM çağrıları ─────────────────────────────────────────────


def _build_content(prompt: str, images: list[bytes]) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for img in images:
        b64 = base64.standard_b64encode(img).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    return content


def _parse_json(raw: str) -> list | dict | None:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for s_char, e_char in [("[", "]"), ("{", "}")]:
            s, e = raw.find(s_char), raw.rfind(e_char)
            if s != -1 and e > s:
                try:
                    return json.loads(raw[s : e + 1])
                except json.JSONDecodeError:
                    continue
    return None


async def extract_answer_key(client: AsyncOpenAI, images: list[bytes]) -> dict[str, dict[int, str]]:
    """
    Cevap anahtarı sayfalarından soru_no → harf eşleştirmesini çıkarır.
    Döndürür: {"TEST-1": {1: "D", 2: "A", ...}, ...}
    """
    prompt = (
        "Bu sayfalardaki CEVAP ANAHTARINI oku.\n"
        "Her test için soru numarası → doğru cevap harfi eşleştirmesini JSON olarak döndür.\n"
        "Sadece JSON, başka metin yazma:\n"
        '{"TYT TARAMA TESTİ-1": {"1": "D", "2": "E"}, "TYT TARAMA TESTİ-2": {"1": "A"}}\n'
        'Test isimleri yoksa: {"default": {"1": "D", "2": "E"}}'
    )
    resp = await client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": _build_content(prompt, images)}],
    )
    data = _parse_json(resp.choices[0].message.content or "")
    if not isinstance(data, dict):
        return {}
    return {
        test: {int(k): v.upper().strip() for k, v in answers.items() if str(k).isdigit()}
        for test, answers in data.items()
        if isinstance(answers, dict)
    }


async def extract_questions(client: AsyncOpenAI, images: list[bytes]) -> list[dict]:
    """
    Soru sayfalarından soruları çıkarır.
    Döndürür: [{"soru_no":1, "test_adi":"...", "question_text":"...",
                "options":["A)...","B)...","C)...","D)...","E)..."], "difficulty":"medium"}]
    """
    prompt = (
        "Bu sayfalardaki çoktan seçmeli soruları çıkar.\n"
        "Sadece JSON array döndür:\n"
        "[\n"
        "  {\n"
        '    "soru_no": 1,\n'
        '    "test_adi": "TYT TARAMA TESTİ-1",\n'
        '    "question_text": "Sorunun tam metni",\n'
        '    "options": ["A) ...", "B) ...", "C) ...", "D) ...", "E) ..."],\n'
        '    "difficulty": "easy",\n'
        '    "explanation": "Bu soru ... konusunu ölçer. Çözüm için ... gerekir."\n'
        "  }\n"
        "]\n"
        "difficulty kriterleri:\n"
        "  easy   — tek adım, doğrudan bilgi sorusu\n"
        "  medium — birden fazla kavramı birleştirme gerektirir\n"
        "  hard   — çok adımlı çıkarım veya karmaşık hesaplama\n"
        "explanation: sorunun ölçtüğü konuyu ve çözüm yaklaşımını 1-2 cümleyle açıkla (Türkçe)\n"
        "- Türkçe karakterleri koru\n"
        "- Test adı sayfada görünmüyorsa test_adi boş bırak\n"
        "- Soru yoksa [] döndür"
    )
    resp = await client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": _build_content(prompt, images)}],
    )
    data = _parse_json(resp.choices[0].message.content or "")
    return data if isinstance(data, list) else []


# ── Cevap eşleştirme ──────────────────────────────────────────


def _find_option(options: list[str], letter: str) -> str:
    letter = letter.upper()
    for opt in options:
        stripped = opt.strip().upper()
        if stripped.startswith(letter + ")") or stripped.startswith(letter + " "):
            return opt
    return ""


def _best_key_for(test_adi: str, answer_key: dict[str, dict[int, str]]) -> str | None:
    if not answer_key:
        return None
    if not test_adi:
        return "default" if "default" in answer_key else list(answer_key.keys())[0]
    test_lower = test_adi.lower()
    for key in answer_key:
        if key.lower() in test_lower or test_lower in key.lower():
            return key
    m = re.search(r"\d+", test_adi)
    if m:
        num = m.group()
        for key in answer_key:
            if re.search(r"\b" + num + r"\b", key):
                return key
    return "default" if "default" in answer_key else list(answer_key.keys())[0]


def resolve_correct_answers(questions: list[dict], answer_key: dict[str, dict[int, str]]) -> list[dict]:
    for q in questions:
        matched_key = _best_key_for(q.get("test_adi", ""), answer_key)
        soru_no = q.get("soru_no")
        letter = answer_key.get(matched_key or "", {}).get(soru_no, "")
        q["correct_answer"] = _find_option(q.get("options", []), letter) if letter else ""
    return questions


# ── Veritabanı ────────────────────────────────────────────────


async def insert_questions(session_factory, kc_id: str, questions: list[dict]) -> int:
    inserted = 0
    async with session_factory() as session:
        for q in questions:
            q_text = (q.get("question_text") or "").strip()
            options = q.get("options") or []
            if not q_text or len(options) < 2:
                continue
            await session.execute(
                sa_text("""
                    INSERT INTO question_bank
                      (id, kc_id, question_text, options, correct_answer, explanation, difficulty)
                    VALUES
                      (:id, :kc_id, :q, CAST(:opts AS jsonb), :ans, :exp, :diff)
                    ON CONFLICT DO NOTHING
                """).bindparams(
                    id=_question_id(kc_id, q_text),
                    kc_id=kc_id,
                    q=q_text,
                    opts=json.dumps(options, ensure_ascii=False),
                    ans=q.get("correct_answer") or "",
                    exp=q.get("explanation") or "",
                    diff=q.get("difficulty") or "medium",
                )
            )
            inserted += 1
        await session.commit()
    return inserted


# ── Ana işlem ─────────────────────────────────────────────────


async def process_pdf(pdf_path: Path, kc_id: str, client: AsyncOpenAI, session_factory) -> int:
    print(f"\n{'='*60}")
    print(f"{pdf_path.name}  →  kc_id: {kc_id}")

    doc = fitz.open(stream=pdf_path.read_bytes(), filetype="pdf")
    n = len(doc)
    print(f"  {n} sayfa")

    # 1. Cevap anahtarı
    ak_indices = find_answer_key_indices(doc)
    print(f"  Cevap anahtarı sayfaları: {[i + 1 for i in ak_indices]}", end=" ", flush=True)
    ak_images = [page_to_jpeg(doc[i]) for i in ak_indices]
    answer_key = await extract_answer_key(client, ak_images)
    total_answers = sum(len(v) for v in answer_key.values())
    print(f"→ {total_answers} cevap: {list(answer_key.keys())}")

    # 2. Soru sayfaları
    ak_set = set(ak_indices)
    q_indices = [i for i in range(n) if i not in ak_set]
    total_inserted = 0

    for chunk_start in range(0, len(q_indices), PAGES_PER_CHUNK):
        chunk = q_indices[chunk_start : chunk_start + PAGES_PER_CHUNK]
        page_nums = [i + 1 for i in chunk]
        print(f"  Sayfalar {page_nums}...", end=" ", flush=True)

        images = [page_to_jpeg(doc[i]) for i in chunk]

        for attempt in range(3):
            try:
                questions = await extract_questions(client, images)
                break
            except Exception as exc:
                if attempt == 2:
                    print(f"HATA (3 deneme): {exc}")
                    questions = []
                    break
                wait = 5 * (attempt + 1)
                print(f"bağlantı hatası, {wait}s sonra tekrar...", end=" ", flush=True)
                await asyncio.sleep(wait)

        if not questions:
            print("soru bulunamadı.")
            continue

        questions = resolve_correct_answers(questions, answer_key)
        matched = sum(1 for q in questions if q.get("correct_answer"))
        n_ins = await insert_questions(session_factory, kc_id, questions)
        total_inserted += n_ins
        print(f"{n_ins} soru eklendi ({matched}/{len(questions)} cevap eşleşti).")

    print(f"  → Toplam {total_inserted} soru: {pdf_path.name}")
    return total_inserted


async def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pdf", help="Tek PDF dosyası")
    group.add_argument("--folder", help="PDF klasörü (*.pdf)")
    parser.add_argument("--kc-id", dest="kc_id", default="", help="kc_id (varsayılan: dosya adından türetilir)")
    parser.add_argument("--skip", nargs="*", default=[], help="Atlanacak PDF dosya adları, ör: --skip tyt_biyoloji.pdf tyt_cografya.pdf")
    parser.add_argument("--model", default=VISION_MODEL, help=f"Vision modeli (varsayılan: {VISION_MODEL})")
    args = parser.parse_args()

    pdfs = [Path(args.pdf)] if args.pdf else sorted(Path(args.folder).glob("*.pdf"))
    if not pdfs or not pdfs[0].exists():
        print(f"PDF bulunamadı: {pdfs}")
        return

    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.novita_api_key,
        base_url=NOVITA_BASE_URL,
        timeout=120.0,
    )
    init_db(settings)
    session_factory = get_session_factory()

    print(f"Model: {args.model}")
    skip_set = {s.lower() for s in args.skip}
    grand_total = 0
    for pdf in pdfs:
        if pdf.name.lower() in skip_set:
            print(f"Atlanıyor: {pdf.name}")
            continue
        kc_id = args.kc_id or pdf.stem.lower()
        try:
            grand_total += await process_pdf(pdf, kc_id, client, session_factory)
        except KeyboardInterrupt:
            print("\nDurduruldu.")
            break

    print(f"\n{'='*60}")
    print(f"TAMAMLANDI — {grand_total} soru question_bank'a eklendi.")


if __name__ == "__main__":
    asyncio.run(main())
