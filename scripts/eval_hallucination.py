"""
Hallucination Evaluation — DB'deki hallucination loglarından istatistik çıkarır.

Kullanım: python scripts/eval_hallucination.py

Metrikler:
  - Ortalama hallucination skoru
  - Yüksek riskli yanıt oranı (skor > 0.7)
  - Zaman bazlı trend
"""
import asyncio
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.settings import get_settings
from app.infrastructure.database import init_db, get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def eval_hallucination():
    """
    hallucination_logs tablosundan kayıtları çekip analiz eder:
    1. Ortalama hallucination skoru
    2. Yüksek riskli (skor > 0.7) yanıt sayısı ve oranı
    3. Son 7 güne göre trend
    """
    settings = get_settings()
    init_db(settings)
    session_factory = get_session_factory()

    logger.info("=" * 60)
    logger.info("Hallucination Monitoring Evaluation")
    logger.info("=" * 60)

    async with session_factory() as session:
        # 1. Genel istatistikler
        result = await session.execute(text("""
            SELECT 
                COUNT(*) as total,
                AVG(score) as avg_score,
                MIN(score) as min_score,
                MAX(score) as max_score,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY score) as median_score,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY score) as p95_score
            FROM hallucination_logs
        """))
        row = result.first()

        if not row or row[0] == 0:
            logger.warning("hallucination_logs tablosunda kayıt bulunamadı.")
            logger.warning("Sistem kullanıldıkça otomatik olarak doldurulur.")
            logger.info("Total Responses Evaluated: 0")
            logger.info("Average Hallucination Score: N/A")
            return

        total = row[0]
        avg_score = float(row[1]) if row[1] is not None else 0
        min_score = float(row[2]) if row[2] is not None else 0
        max_score = float(row[3]) if row[3] is not None else 0
        median_score = float(row[4]) if row[4] is not None else 0
        p95_score = float(row[5]) if row[5] is not None else 0

        logger.info("Total Responses Evaluated: %d", total)
        logger.info("Average Hallucination Score: %.4f", avg_score)
        logger.info("Median: %.4f | Min: %.4f | Max: %.4f | P95: %.4f",
                     median_score, min_score, max_score, p95_score)

        # 2. Yüksek riskli yanıtlar (skor > 0.7)
        result = await session.execute(text("""
            SELECT COUNT(*) FROM hallucination_logs WHERE score > 0.7
        """))
        high_risk_count = result.scalar() or 0
        high_risk_pct = (high_risk_count / total * 100) if total > 0 else 0

        logger.info("-" * 40)
        logger.info("🚨 High Risk (score > 0.7): %d / %d (%.1f%%)", high_risk_count, total, high_risk_pct)

        # Risk seviyeleri
        result = await session.execute(text("""
            SELECT 
                SUM(CASE WHEN score <= 0.3 THEN 1 ELSE 0 END) as low,
                SUM(CASE WHEN score > 0.3 AND score <= 0.7 THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN score > 0.7 THEN 1 ELSE 0 END) as high
            FROM hallucination_logs
        """))
        risk_row = result.first()
        if risk_row:
            logger.info("Risk Distribution — Low(≤0.3): %d | Medium(0.3-0.7): %d | High(>0.7): %d",
                         risk_row[0] or 0, risk_row[1] or 0, risk_row[2] or 0)

        # 3. Son 7 gün bazında günlük trend
        logger.info("-" * 40)
        logger.info("Daily Trend (Last 7 Days):")

        result = await session.execute(text("""
            SELECT 
                DATE(created_at) as day,
                COUNT(*) as cnt,
                AVG(score) as avg_s,
                SUM(CASE WHEN score > 0.7 THEN 1 ELSE 0 END) as high_cnt
            FROM hallucination_logs
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY day DESC
        """))
        trend_rows = result.fetchall()

        if trend_rows:
            for tr in trend_rows:
                day_str = str(tr[0])
                cnt = tr[1]
                avg_s = float(tr[2]) if tr[2] else 0
                high = tr[3] or 0
                bar = "█" * int(avg_s * 20) + "░" * (20 - int(avg_s * 20))
                logger.info("  %s | n=%d | avg=%.3f |%s| high=%d", day_str, cnt, avg_s, bar, high)
        else:
            logger.info("  Son 7 günde veri yok.")

        # 4. En kötü 5 yanıt
        logger.info("-" * 40)
        logger.info("Worst 5 Responses:")
        result = await session.execute(text("""
            SELECT score, assistant_response, created_at
            FROM hallucination_logs
            ORDER BY score DESC
            LIMIT 5
        """))
        worst = result.fetchall()
        for i, w in enumerate(worst, 1):
            score = float(w[0]) if w[0] else 0
            resp = (w[1] or "")[:100]
            logger.info("  #%d score=%.3f | %s...", i, score, resp)

    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(eval_hallucination())
