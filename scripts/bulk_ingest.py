"""
Bulk Ingest Script — Belirtilen klasördeki dökümanları (PDF, TXT, MD) sisteme toplu yükler.
Kullanım: python scripts/bulk_ingest.py --folder ./docs --document_id "mufredat_v1"
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

# App dizinini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory
from app.api.dependencies import get_ingestion_pipeline
from app.services.content_rag.chunker import Chunker
from app.infrastructure.embedder_factory import build_embedder
from app.infrastructure.pg_vector_store import PgVectorStore

async def process_file(pipeline, session, file_path, document_id, kc_tags):
    ext = file_path.suffix.lower()
    print(f"İşleniyor: {file_path.name} ({ext})")
    
    try:
        if ext == ".pdf":
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            await pipeline.ingest_pdf(
                session=session,
                document_id=document_id,
                pdf_bytes=pdf_bytes,
                kc_tags=kc_tags,
                metadata={"filename": file_path.name}
            )
        elif ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            await pipeline.ingest_text(
                session=session,
                document_id=document_id,
                text=text,
                kc_tags=kc_tags,
                metadata={"filename": file_path.name},
                replace_existing=False # Aynı document_id içine ekle
            )
        else:
            print(f"Atlanıyor (desteklenmeyen format): {file_path.name}")
            return False
        return True
    except Exception as e:
        print(f"Hata ({file_path.name}): {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Toplu döküman yükleme")
    parser.add_argument("--folder", required=True, help="Dökümanların bulunduğu klasör yolu")
    parser.add_argument("--document_id", default="global_knowledge", help="Döküman grubu ID'si")
    parser.add_argument("--tags", default="", help="Virgülle ayrılmış KC etiketleri")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()
    
    embedder = await build_embedder(settings)
    store = PgVectorStore()
    pipeline = get_ingestion_pipeline(
        chunker=Chunker(),
        embedder=embedder,
        vector_store=store
    )

    folder_path = Path(args.folder)
    if not folder_path.is_dir():
        print(f"Hata: {args.folder} bir klasör değil.")
        return

    kc_tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    files = list(folder_path.glob("*"))
    
    print(f"Toplam {len(files)} dosya bulundu. Başlanıyor...")

    async with session_factory() as session:
        success_count = 0
        for file_path in files:
            if file_path.is_file():
                if await process_file(pipeline, session, file_path, args.document_id, kc_tags):
                    success_count += 1
        
        await session.commit()
        print(f"\nİşlem tamamlandı! {success_count}/{len(files)} dosya başarıyla yüklendi.")

if __name__ == "__main__":
    asyncio.run(main())
