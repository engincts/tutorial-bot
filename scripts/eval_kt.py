"""
Knowledge Tracing Evaluation — Gerçek DB'den veri çekip AUC hesaplar.

Kullanım: python scripts/eval_kt.py

Metrik: ROC-AUC — KT modelinin "öğrenci bu soruyu doğru yapacak mı?"
tahmininin gerçek sonuçla ne kadar örtüştüğünü ölçer.
"""
import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory
from app.services.knowledge_tracing import build_tracer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def eval_kt():
    """
    1. chat_history tablosundan correctness != NULL olan etkileşimleri çeker
    2. Her etkileşim için KT modelinden o ana kadarki p_mastery tahminini alır
    3. Gerçek correctness ile karşılaştırarak AUC hesaplar
    """
    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()
    tracer = build_tracer(settings.kt_model)

    logger.info("=" * 60)
    logger.info("Knowledge Tracing Evaluation")
    logger.info("Model: %s", settings.kt_model)
    logger.info("=" * 60)

    # DB'den correctness bilgisi olan etkileşimleri çek (kronolojik sırayla)
    query = text("""
        SELECT learner_id, kc_tags, correctness, created_at
        FROM chat_history
        WHERE correctness IS NOT NULL
          AND array_length(kc_tags, 1) > 0
        ORDER BY learner_id, created_at ASC
    """)

    predictions = []
    actuals = []

    async with session_factory() as session:
        result = await session.execute(query)
        rows = result.fetchall()

    if not rows:
        logger.warning("DB'de correctness verisi bulunamadı.")
        logger.warning("Önce sistemi kullanarak etkileşim verisi oluşturun.")
        logger.info("Total Interactions: 0")
        logger.info("AUC: N/A (veri yok)")
        return

    logger.info("Toplam %d etkileşim bulundu.", len(rows))

    # Her etkileşimi sırayla işle — KT modelini simüle et
    for row in rows:
        learner_id = row[0]
        kc_tags = row[1] or []
        correct = row[2]

        for kc_id in kc_tags:
            # Tahmin al (güncelleme öncesi)
            mastery_map = await tracer.estimate(learner_id, [kc_id])
            p_mastery = mastery_map.get(kc_id, 0.3)

            predictions.append(p_mastery)
            actuals.append(1 if correct else 0)

            # Modeli güncelle (sonraki tahmin için)
            await tracer.update(learner_id, kc_id, correct)

    # AUC hesapla
    logger.info("-" * 40)
    logger.info("Evaluation Results:")
    logger.info("Total Interactions Evaluated: %d", len(predictions))

    if len(set(actuals)) < 2:
        logger.warning("Sadece tek sınıf var (hep doğru veya hep yanlış) — AUC hesaplanamaz.")
        logger.info("Correct ratio: %.2f", sum(actuals) / len(actuals) if actuals else 0)
        return

    try:
        from sklearn.metrics import roc_auc_score, accuracy_score
        auc = roc_auc_score(actuals, predictions)
        # Binary accuracy (threshold=0.5)
        binary_preds = [1 if p >= 0.5 else 0 for p in predictions]
        acc = accuracy_score(actuals, binary_preds)

        logger.info("AUC: %.4f", auc)
        logger.info("Accuracy (threshold=0.5): %.4f", acc)
        logger.info("Correct Ratio: %.2f%%", 100 * sum(actuals) / len(actuals))

        # Kalibrasyon: ortalama tahmin vs gerçek oran
        avg_pred = sum(predictions) / len(predictions)
        avg_actual = sum(actuals) / len(actuals)
        logger.info("Avg Prediction: %.4f | Avg Actual: %.4f | Calibration Gap: %.4f",
                     avg_pred, avg_actual, abs(avg_pred - avg_actual))

    except ImportError:
        logger.error("scikit-learn yüklü değil. AUC hesabı için: pip install scikit-learn")
        # Manuel AUC yaklaşımı
        correct_count = sum(actuals)
        total = len(actuals)
        logger.info("Doğru: %d / %d (%.1f%%)", correct_count, total, 100 * correct_count / total)

    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(eval_kt())
