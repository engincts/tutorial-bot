"""
Reranker — pgvector'dan gelen chunk'ları LLM ile yeniden sıralar.

pgvector cosine similarity iyi bir sıralama yapar, ancak semantic
relevance her zaman query intent'iyle örtüşmez. Bu reranker LLM'e
her chunk için 0-10 arası bir relevance skoru verdirerek yeniden sıralar.

Sadece rerank_enabled=True olduğunda çağrılır (settings).
"""
from __future__ import annotations

import json
import logging
import re

from app.infrastructure.llm.base import BaseLLMClient, Message
from app.services.content_rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)

_SYSTEM = """\
Verilen sorgu için her kaynak chunk'ının ne kadar alakalı olduğunu puanla.
SADECE JSON döndür:
{"scores": [<chunk_1_skoru>, <chunk_2_skoru>, ...]}
Skorlar 0-10 arası tam sayı. Listedeki eleman sayısı chunk sayısıyla aynı olsun.
"""


class Reranker:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self._llm = llm_client

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Chunk'ları LLM ile puanlar ve yeniden sıralar.
        Hata durumunda orijinal sırayla döner.
        top_k verilirse sadece ilk top_k chunk'ı döner.
        """
        if not chunks:
            return chunks

        try:
            chunk_texts = "\n\n".join(
                f"[{i}] {chunk.content[:200]}"
                for i, chunk in enumerate(chunks)
            )
            user_content = f"Sorgu: {query[:300]}\n\nChunk'lar:\n{chunk_texts}"

            response = await self._llm.complete(
                messages=[
                    Message(role="system", content=_SYSTEM),
                    Message(role="user", content=user_content),
                ],
                temperature=0.0,
                max_tokens=100,
            )
            raw = response.content.strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return chunks[:top_k] if top_k else chunks

            data = json.loads(match.group())
            scores: list[int] = data.get("scores", [])

            if len(scores) != len(chunks):
                return chunks[:top_k] if top_k else chunks

            ranked = sorted(
                zip(chunks, scores),
                key=lambda x: x[1],
                reverse=True,
            )
            result = [chunk for chunk, _ in ranked]
            return result[:top_k] if top_k else result

        except Exception as exc:
            logger.debug("Reranker başarısız, orijinal sıra kullanılıyor: %s", exc)
            return chunks[:top_k] if top_k else chunks
