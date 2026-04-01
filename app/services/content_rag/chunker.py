"""
Structure-aware text chunker.
Markdown başlıklarına, paragraflara ve cümle sınırlarına saygı gösterir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    char_start: int
    char_end: int
    heading: str = ""


class Chunker:
    """
    1) Markdown başlıklarında böl
    2) Bölüm max_chars'ı aşıyorsa paragraf → cümle sınırlarında böl
    3) overlap_chars kadar önceki metni her chunk'a ekle
    """

    def __init__(
        self,
        max_chars: int = 1500,
        overlap_chars: int = 150,
    ) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, text: str) -> list[TextChunk]:
        sections = self._split_by_headings(text)
        chunks: list[TextChunk] = []
        global_index = 0
        char_cursor = 0

        for heading, section_text in sections:
            section_chunks = self._split_section(section_text)
            for chunk_text in section_chunks:
                if not chunk_text.strip():
                    continue
                start = char_cursor
                end = char_cursor + len(chunk_text)
                chunks.append(
                    TextChunk(
                        text=chunk_text.strip(),
                        chunk_index=global_index,
                        char_start=start,
                        char_end=end,
                        heading=heading,
                    )
                )
                global_index += 1
                char_cursor = end

        return self._apply_overlap(chunks)

    # ── Private helpers ───────────────────────────────────────────────

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """Markdown h1-h3 başlıklarına göre bölümlere ayır."""
        pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(text))

        if not matches:
            return [("", text)]

        sections: list[tuple[str, str]] = []
        # Başlıktan önceki kısım
        if matches[0].start() > 0:
            sections.append(("", text[: matches[0].start()]))

        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            content_start = match.end()
            content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((heading, text[content_start:content_end]))

        return sections

    def _split_section(self, text: str) -> list[str]:
        """Bir bölümü max_chars sınırında parçalara böl."""
        if len(text) <= self.max_chars:
            return [text]

        # Önce paragraflara böl
        paragraphs = re.split(r"\n\n+", text)
        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 <= self.max_chars:
                current = (current + "\n\n" + para).lstrip()
            else:
                if current:
                    chunks.append(current)
                # Paragraf tek başına max_chars'ı aşıyorsa cümlelere böl
                if len(para) > self.max_chars:
                    chunks.extend(self._split_by_sentences(para))
                    current = ""
                else:
                    current = para

        if current:
            chunks.append(current)

        return chunks

    def _split_by_sentences(self, text: str) -> list[str]:
        """Cümle sınırlarında böl — son çare."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= self.max_chars:
                current = (current + " " + sentence).lstrip()
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks

    def _apply_overlap(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """Her chunk'ın başına bir önceki chunk'tan overlap_chars kadar metin ekle."""
        if self.overlap_chars <= 0 or len(chunks) < 2:
            return chunks

        result: list[TextChunk] = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_text = chunks[i - 1].text
            overlap = prev_text[-self.overlap_chars :] if len(prev_text) > self.overlap_chars else prev_text
            new_text = overlap + "\n" + chunks[i].text
            result.append(
                TextChunk(
                    text=new_text,
                    chunk_index=chunks[i].chunk_index,
                    char_start=chunks[i].char_start,
                    char_end=chunks[i].char_end,
                    heading=chunks[i].heading,
                )
            )

        return result
