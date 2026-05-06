"""
Seed script to populate curriculum_chunks with sample data.
Uses direct DB access to bypass JWT requirements for initial setup.
"""
import asyncio
import uuid
import sys
import os

# App dizinini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory
from app.api.dependencies import get_ingestion_pipeline

SAMPLE_DATA = [
    {
        "id": "tyt_matematik",
        "kc": "matematik_sayilar_dogal_sayilar",
        "text": "# Doğal Sayılar\nDoğal sayılar 0'dan başlayıp sonsuza giden tam sayılardır. N = {0, 1, 2, ...} şeklinde gösterilir."
    },
    {
        "id": "tyt_matematik",
        "kc": "matematik_sayilar_tam_sayilar",
        "text": "# Tam Sayılar\nTam sayılar kümesi, doğal sayılar ile bunların negatiflerinin birleşimidir. Z = {..., -2, -1, 0, 1, 2, ...} şeklinde gösterilir."
    },
    {
        "id": "tyt_fizik",
        "kc": "fizik_kuvvet_newton_yasaları",
        "text": "# Newton'ın Hareket Yasaları\n1. Eylemsizlik Prensibi\n2. Dinamiğin Temel Prensibi (F=ma)\n3. Etki-Tepki Prensibi"
    }
]

async def seed():
    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()
    
    # IngestionPipeline manual init
    from app.services.content_rag.chunker import Chunker
    from app.infrastructure.embedder_factory import build_embedder
    from app.infrastructure.pg_vector_store import PgVectorStore
    
    embedder = await build_embedder(settings)
    store = PgVectorStore()
    pipeline = get_ingestion_pipeline(
        chunker=Chunker(),
        embedder=embedder,
        vector_store=store
    )

    async with session_factory() as session:
        for item in SAMPLE_DATA:
            print(f"Ingesting {item['kc']} into {item['id']}...")
            await pipeline.ingest_text(
                session=session,
                document_id=item["id"],
                text=item["text"],
                kc_tags=[item["kc"]],
                replace_existing=False # Birden fazla KC aynı document_id'de olabilir
            )
        await session.commit()
    print("Seed tamamlandı.")

if __name__ == "__main__":
    asyncio.run(seed())
