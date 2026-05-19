"""
Bulk Ingest Script — Klasördeki PDF/TXT/MD dökümanlarını sisteme toplu yükler.

Kullanım örnekleri:
  # Her dosya kendi isminden document_id alır (tyt_matematik.pdf → tyt_matematik)
  python scripts/bulk_ingest.py --folder /path/to/pdfs

  # Tüm dosyalara aynı document_id ver
  python scripts/bulk_ingest.py --folder ./docs --document_id mufredat_v1

  # KC etiketlerini elle belirt (auto modda dosya adından da türetilir)
  python scripts/bulk_ingest.py --folder ./docs --tags matematik,fizik
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory
from app.api.dependencies import get_ingestion_pipeline
from app.services.content_rag.chunker import Chunker
from app.infrastructure.embedder_factory import build_embedder
from app.infrastructure.pg_vector_store import PgVectorStore


def derive_doc_id_and_tags(file_path: Path, fallback_doc_id: str) -> tuple[str, list[str]]:
    """
    Dosya adından document_id ve KC etiketleri türetir.
    Örnek: tyt_matematik.pdf → ("tyt_matematik", ["matematik"])
    """
    stem = file_path.stem.lower()  # "tyt_matematik"
    parts = stem.split("_")       # ["tyt", "matematik"]
    # İlk part prefix (tyt/ayt), geri kalanlar ders adı
    if len(parts) >= 2:
        ders = "_".join(parts[1:])   # "matematik"
        return stem, [ders]
    return fallback_doc_id or stem, []


async def process_file(
    pipeline,
    session,
    file_path: Path,
    document_id: str,
    kc_tags: list[str],
) -> bool:
    ext = file_path.suffix.lower()
    print(f"  [{document_id}] {file_path.name} işleniyor... (kc_tags={kc_tags})")

    try:
        if ext == ".pdf":
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            await pipeline.ingest_pdf(
                session=session,
                document_id=document_id,
                pdf_bytes=pdf_bytes,
                kc_tags=kc_tags,
                metadata={"filename": file_path.name},
            )
        elif ext in (".txt", ".md"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            await pipeline.ingest_text(
                session=session,
                document_id=document_id,
                text=text,
                kc_tags=kc_tags,
                metadata={"filename": file_path.name},
                replace_existing=False,
            )
        else:
            print(f"  Atlanıyor (desteklenmeyen format): {file_path.name}")
            return False
        return True
    except Exception as e:
        print(f"  HATA ({file_path.name}): {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Toplu döküman yükleme")
    parser.add_argument("--folder", required=True, help="Dökümanların bulunduğu klasör")
    parser.add_argument(
        "--document_id",
        default="",
        help="Döküman ID'si. Boş bırakılırsa dosya adından otomatik türetilir.",
    )
    parser.add_argument(
        "--tags",
        default="",
        help="Virgülle ayrılmış ek KC etiketleri (auto modda dosya adından gelen etiketlere eklenir)",
    )
    args = parser.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.is_dir():
        print(f"Hata: '{args.folder}' bir klasör değil.")
        return

    extra_tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()

    embedder = await build_embedder(settings)
    store = PgVectorStore()
    pipeline = get_ingestion_pipeline(
        chunker=Chunker(),
        embedder=embedder,
        vector_store=store,
    )

    files = sorted(f for f in folder_path.iterdir() if f.is_file())
    print(f"{len(files)} dosya bulundu → {folder_path}")

    success, failed = 0, 0
    for file_path in files:
        doc_id, auto_tags = derive_doc_id_and_tags(file_path, args.document_id)
        if args.document_id:
            doc_id = args.document_id  # elle belirtilmişse onu kullan
        kc_tags = list(dict.fromkeys(auto_tags + extra_tags))  # deduplicate

        async with session_factory() as session:
            ok = await process_file(pipeline, session, file_path, doc_id, kc_tags)
            if ok:
                await session.commit()
                success += 1
            else:
                failed += 1

    print(f"\nTamamlandı: {success} başarılı, {failed} başarısız.")


if __name__ == "__main__":
    asyncio.run(main())
