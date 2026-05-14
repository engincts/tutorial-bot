"""
Retrieval Evaluation — RAG pipeline'ın Recall@k ve MRR metriklerini hesaplar.

Kullanım: python scripts/eval_retrieval.py

Metrikler:
  - Recall@k: Beklenen dokümanın ilk k sonuç içinde bulunma oranı
  - MRR (Mean Reciprocal Rank): Beklenen dokümanın sırasının tersi ortalaması
  - NDCG@k: Sıralama kalitesi (normalized discounted cumulative gain)
"""
import asyncio
import logging
import sys
import os
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory
from app.api.dependencies import get_content_retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# Ground truth: sorgu → beklenen document_id eşlemeleri
# Sisteme yüklediğin dökümanların ID'leriyle eşleştir
STATIC_TEST_DATA = [
    {"query": "Doğal sayılar nedir?", "expected_doc_ids": ["tyt_matematik"]},
    {"query": "Tam sayılar kümesi", "expected_doc_ids": ["tyt_matematik"]},
    {"query": "Newton hareket yasaları", "expected_doc_ids": ["tyt_fizik"]},
    {"query": "F=ma formülü", "expected_doc_ids": ["tyt_fizik"]},
]


async def build_test_data_from_db(session_factory) -> list[dict]:
    """DB'deki mevcut dökümanlardan otomatik test verisi oluştur."""
    test_data = list(STATIC_TEST_DATA)

    async with session_factory() as session:
        # Mevcut dokümanlardan benzersiz document_id'leri çek
        result = await session.execute(
            text("SELECT DISTINCT document_id FROM curriculum_chunks LIMIT 20")
        )
        doc_ids = [row[0] for row in result.fetchall()]

        if not doc_ids:
            logger.warning("DB'de döküman bulunamadı. Sadece statik test verisi kullanılacak.")
            return test_data

        # Her doküman için ilk chunk'ın içeriğinden sorgu üret
        for doc_id in doc_ids:
            result = await session.execute(
                text("""
                    SELECT content FROM curriculum_chunks 
                    WHERE document_id = :doc_id 
                    ORDER BY chunk_index 
                    LIMIT 1
                """).bindparams(doc_id=doc_id)
            )
            row = result.first()
            if row and row[0]:
                # İçeriğin ilk 80 karakterini sorgu olarak kullan
                content_snippet = row[0][:80].strip()
                if content_snippet:
                    test_data.append({
                        "query": content_snippet,
                        "expected_doc_ids": [doc_id],
                    })

    return test_data


def dcg_at_k(relevances: list[int], k: int) -> float:
    """Discounted Cumulative Gain hesapla."""
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances[:k]))


def ndcg_at_k(relevances: list[int], k: int) -> float:
    """Normalized DCG hesapla."""
    dcg = dcg_at_k(relevances, k)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)
    return dcg / ideal if ideal > 0 else 0.0


async def eval_retrieval():
    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()
    retriever = get_content_retriever()

    logger.info("=" * 60)
    logger.info("Retrieval Pipeline Evaluation")
    logger.info("=" * 60)

    test_data = await build_test_data_from_db(session_factory)
    logger.info("Test sorgu sayısı: %d", len(test_data))

    k_values = [1, 3, 5]
    results = {k: {"hits": 0, "mrr_sum": 0.0, "ndcg_sum": 0.0} for k in k_values}
    total_queries = 0
    failed_queries = 0

    async with session_factory() as session:
        for item in test_data:
            try:
                embedding = await retriever.embed(item["query"])
                chunks = await retriever.retrieve(
                    session, 
                    query=item["query"], 
                    embedding=embedding,
                    top_k=max(k_values),
                )
                retrieved_docs = [chunk.document_id for chunk in chunks]
                total_queries += 1

                for k in k_values:
                    top_docs = retrieved_docs[:k]
                    # Hit kontrolü
                    hit = any(exp_id in top_docs for exp_id in item["expected_doc_ids"])
                    if hit:
                        results[k]["hits"] += 1
                        # MRR: ilk eşleşmenin sırası
                        for rank, doc_id in enumerate(top_docs, 1):
                            if doc_id in item["expected_doc_ids"]:
                                results[k]["mrr_sum"] += 1.0 / rank
                                break

                    # NDCG
                    relevances = [1 if d in item["expected_doc_ids"] else 0 for d in top_docs]
                    results[k]["ndcg_sum"] += ndcg_at_k(relevances, k)

                status = "✅ HIT" if any(e in retrieved_docs for e in item["expected_doc_ids"]) else "❌ MISS"
                logger.info("%s | query='%s' | retrieved=%s", status, item["query"][:50], retrieved_docs[:3])

            except Exception as e:
                failed_queries += 1
                logger.error("Sorgu başarısız: '%s' — %s", item["query"][:50], e)

    # Sonuçlar
    logger.info("=" * 60)
    logger.info("RESULTS")
    logger.info("-" * 40)

    if total_queries == 0:
        logger.warning("Hiç sorgu çalıştırılamadı.")
        return

    for k in k_values:
        recall = results[k]["hits"] / total_queries
        mrr = results[k]["mrr_sum"] / total_queries
        ndcg = results[k]["ndcg_sum"] / total_queries
        logger.info("Recall@%d: %.4f  |  MRR@%d: %.4f  |  NDCG@%d: %.4f", k, recall, k, mrr, k, ndcg)

    logger.info("-" * 40)
    logger.info("Total Queries: %d | Failed: %d", total_queries, failed_queries)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(eval_retrieval())
