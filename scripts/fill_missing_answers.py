"""
question_bank tablosunda correct_answer boş olan soruların cevabını LLM ile çıkarır.

Kullanım:
  python scripts/fill_missing_answers.py
  python scripts/fill_missing_answers.py --kc-id tyt_biyoloji
  python scripts/fill_missing_answers.py --dry-run   # DB'ye yazmadan göster
"""

import asyncio
import argparse
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
import ssl
from openai import AsyncOpenAI

from app.settings import get_settings

NOVITA_BASE_URL = "https://api.novita.ai/v3/openai"
CONCURRENCY = 1
RATE_LIMIT_SLEEP = 2.5  # 24 req/min — Novita free tier: 30 req/min


async def pick_answer(client: AsyncOpenAI, model: str, question_text: str, options: list[str]) -> str:
    opts_formatted = "\n".join(options)
    prompt = (
        f"Aşağıdaki çoktan seçmeli soruyu çöz. Sadece doğru şıkkın tam metnini yaz, başka hiçbir şey yazma.\n\n"
        f"Soru: {question_text}\n\n"
        f"Şıklar:\n{opts_formatted}\n\n"
        f"Doğru şık (tam metin, örnek: 'A) Mitoz bölünme'):"
    )
    resp = await client.chat.completions.create(
        model=model,
        max_tokens=200,
        temperature=0.0,
        messages=[
            {"role": "system", "content": "Sen TYT/AYT soru çözme uzmanısın. Sadece istenen formatta cevap ver."},
            {"role": "user", "content": prompt},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw_upper = raw.upper()
    for opt in options:
        if opt.strip().upper() == raw_upper:
            return opt
    if raw_upper and raw_upper[0] in "ABCDE":
        letter = raw_upper[0]
        for opt in options:
            if opt.strip().upper().startswith(letter + ")") or opt.strip().upper().startswith(letter + " "):
                return opt
    for opt in options:
        if raw[:30].lower() in opt.lower() or opt[:30].lower() in raw.lower():
            return opt
    return raw


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kc-id", dest="kc_id", default="", help="Sadece bu kc_id'yi işle (boşsa hepsi)")
    parser.add_argument("--model", default="", help="Kullanılacak model (boşsa settings.novita_llm_model)")
    parser.add_argument("--dry-run", action="store_true", help="DB'ye yazma, sadece göster")
    args = parser.parse_args()

    settings = get_settings()
    model = args.model or settings.novita_llm_model
    client = AsyncOpenAI(
        api_key=settings.novita_api_key,
        base_url=NOVITA_BASE_URL,
        timeout=60.0,
        max_retries=0,  # SDK retry'ı kapalı — kendi retry logic'imiz var
    )

    ssl_setting = settings.postgres_ssl
    if isinstance(ssl_setting, str) and ssl_setting.lower() == "disable":
        ssl_val: ssl.SSLContext | bool = False
    else:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        ssl_val = ssl_ctx

    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        ssl=ssl_val,
    )

    q = "SELECT id, kc_id, question_text, options FROM question_bank WHERE (correct_answer = '' OR correct_answer IS NULL)"
    if args.kc_id:
        rows = await conn.fetch(q + " AND kc_id ILIKE $1 ORDER BY kc_id, id", f"%{args.kc_id}%")
    else:
        rows = await conn.fetch(q + " ORDER BY kc_id, id")

    if not rows:
        print("Boş cevaplı soru yok.")
        await conn.close()
        return

    print(f"{len(rows)} soru işlenecek | model: {model} | dry-run: {args.dry_run}")

    sem = asyncio.Semaphore(CONCURRENCY)
    updated = 0
    errors = 0

    async def process(row):
        nonlocal updated, errors
        qid = row["id"]
        kc_id = row["kc_id"]
        q_text = row["question_text"]
        opts_raw = row["options"]
        options = opts_raw if isinstance(opts_raw, list) else json.loads(opts_raw)

        async with sem:
            for attempt in range(3):
                try:
                    answer = await pick_answer(client, model, q_text, options)
                    await asyncio.sleep(RATE_LIMIT_SLEEP)
                    break
                except Exception as exc:
                    if attempt == 2:
                        print(f"  HATA [{kc_id}] {q_text[:50]}: {exc}")
                        errors += 1
                        return
                    await asyncio.sleep(15 * (attempt + 1))  # 429 sonrası daha uzun bekle

        short_q = q_text[:60].replace("\n", " ")
        print(f"  [{kc_id}] {short_q}... → {answer[:50]}")

        if not args.dry_run:
            await conn.execute(
                "UPDATE question_bank SET correct_answer = $1 WHERE id = $2",
                answer, qid
            )
        updated += 1

    await asyncio.gather(*[process(r) for r in rows], return_exceptions=True)
    await conn.close()
    print(f"\nTamamlandı — {updated} güncellendi, {errors} hata.")


if __name__ == "__main__":
    asyncio.run(main())
