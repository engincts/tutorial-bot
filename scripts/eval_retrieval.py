import asyncio
import logging
from app.infrastructure.database import get_session_factory
from app.api.dependencies import get_content_retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def eval_retrieval():
    """
    Retrieval pipeline'ı test eder.
    Gerçek verilerle ground truth veri seti oluşturup Recall@k ve MRR hesaplar.
    """
    # Örnek test verisi: "Soru" -> Beklenen "document_id"
    test_data = [
        {"query": "Türev zincir kuralı nedir?", "expected_doc_id": "matematik_turev"},
        {"query": "Mitoz bölünme evreleri nelerdir?", "expected_doc_id": "biyoloji_hucre"},
    ]
    
    retriever = get_content_retriever()
    session_factory = get_session_factory()
    
    hits = 0
    mrr_sum = 0.0
    
    async with session_factory() as session:
        for item in test_data:
            chunks = await retriever.retrieve(session, query=item["query"], top_k=5)
            retrieved_docs = [chunk.document_id for chunk in chunks]
            
            if item["expected_doc_id"] in retrieved_docs:
                hits += 1
                rank = retrieved_docs.index(item["expected_doc_id"]) + 1
                mrr_sum += 1.0 / rank
                logger.info("HIT for '%s' (rank %d)", item["query"], rank)
            else:
                logger.warning("MISS for '%s'", item["query"])
                
    recall = hits / len(test_data) if test_data else 0
    mrr = mrr_sum / len(test_data) if test_data else 0
    
    logger.info("-------------------------")
    logger.info("Evaluation Results:")
    logger.info("Recall@5: %.2f", recall)
    logger.info("MRR: %.2f", mrr)

if __name__ == "__main__":
    asyncio.run(eval_retrieval())
