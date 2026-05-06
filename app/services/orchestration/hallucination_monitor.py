import logging
import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.infrastructure.llm.base import BaseLLMClient, Message

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """\
Sen bir eğitim asistanının yanıtlarını denetleyen bir doğrulayıcısın (LLM-as-judge).
Görevin, asistanın verdiği cevabın "Sağlanan Kaynak İçeriğine" (context) sadık kalıp kalmadığını (hallucination / uydurma) kontrol etmektir.
Asistan, context'te OLMAYAN bir bilgi üretmişse yüksek skor, context'e tamamen sadıksa düşük skor vermelisin.
Skor 0.0 (tamamen sadık) ile 1.0 (tamamen uydurma) arasında olmalıdır.

Dönüş formatı STRICT JSON olmalıdır:
{
  "score": 0.0,
  "reasoning": "Neden bu skoru verdiğinin kısa açıklaması"
}
"""

class HallucinationMonitor:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def evaluate(
        self,
        session: AsyncSession,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        assistant_response: str,
        context_used: str,
    ) -> float:
        """
        Yanıtı değerlendirip skoru döner ve DB'ye kaydeder.
        """
        user_prompt = f"KAYNAK (Context):\n{context_used}\n\nASİSTAN YANITI:\n{assistant_response}"
        
        score = 0.0
        try:
            res = await self._llm.complete(
                messages=[
                    Message(role="system", content=_JUDGE_SYSTEM),
                    Message(role="user", content=user_prompt)
                ],
                temperature=0.0,
                max_tokens=200
            )
            
            import json
            match = re.search(r"\{.*?\}", res.content.strip(), re.DOTALL)
            if match:
                data = json.loads(match.group())
                score = float(data.get("score", 0.0))
        except Exception as e:
            logger.warning("Hallucination check failed: %s", e)
            return 0.0

        # Log it to DB
        await session.execute(
            text("""
                INSERT INTO hallucination_logs (id, learner_id, session_id, score, assistant_response, context_used)
                VALUES (:id, :lid, :sid, :score, :resp, :ctx)
            """).bindparams(
                id=uuid.uuid4(),
                lid=learner_id,
                sid=session_id,
                score=score,
                resp=assistant_response,
                ctx=context_used
            )
        )
        
        if score > 0.7:
            logger.error("🚨 HIGH HALLUCINATION DETECTED: score=%.2f | session=%s", score, session_id)
            
        return score
