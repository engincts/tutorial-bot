"""Chunker testleri — DB gerektirmez."""
import pytest
from app.services.content_rag.chunker import Chunker


class TestChunker:
    def test_short_text_single_chunk(self):
        c = Chunker(max_chars=1500)
        chunks = c.chunk("Kısa bir metin.")
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0

    def test_heading_extraction(self):
        text = "# Türevler\nTürev bir fonksiyonun anlık değişim hızıdır.\n\n## Zincir Kuralı\nf(g(x))"
        c = Chunker(max_chars=1500)
        chunks = c.chunk(text)
        headings = [ch.heading for ch in chunks]
        assert "Türevler" in headings or "Zincir Kuralı" in headings

    def test_long_text_split_into_multiple_chunks(self):
        paragraph = "Bu cümle test amaçlıdır. " * 30  # ~750 char
        text = paragraph + "\n\n" + paragraph + "\n\n" + paragraph
        c = Chunker(max_chars=800, overlap_chars=0)
        chunks = c.chunk(text)
        assert len(chunks) >= 2

    def test_overlap_applied(self):
        para_a = "A harfi içeren cümle. " * 20
        para_b = "B harfi içeren cümle. " * 20
        text = para_a + "\n\n" + para_b
        c = Chunker(max_chars=500, overlap_chars=50)
        chunks = c.chunk(text)
        if len(chunks) >= 2:
            # ikinci chunk öncekinin sonundan overlap içermeli
            assert len(chunks[1].text) > len(para_b.strip())

    def test_chunk_indices_sequential(self):
        text = ("Paragraf içeriği burada. " * 20 + "\n\n") * 5
        c = Chunker(max_chars=300, overlap_chars=0)
        chunks = c.chunk(text)
        indices = [ch.chunk_index for ch in chunks]
        assert indices == list(range(len(chunks)))

    def test_empty_text_returns_empty(self):
        c = Chunker()
        assert c.chunk("") == []
        assert c.chunk("   \n\n   ") == []


class TestChunkerSentenceFallback:
    def test_very_long_paragraph_split(self):
        # tek paragraf, çok uzun
        long_para = "Bu bir test cümlesidir. " * 100  # ~2400 char
        c = Chunker(max_chars=500, overlap_chars=0)
        chunks = c.chunk(long_para)
        assert all(len(ch.text) <= 600 for ch in chunks)  # biraz tolerans
        assert len(chunks) >= 2
