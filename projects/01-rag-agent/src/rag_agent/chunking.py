"""Paragraph-aware recursive chunking.

Chunks are packed from whole paragraphs first; paragraphs longer than the size
budget are split at sentence boundaries, and pathologically long sentences are
split at word boundaries with a word-level overlap. Guarantees (unit-tested):

- every chunk has at most ``size`` whitespace-delimited tokens;
- consecutive word-level splits share exactly ``overlap`` trailing/leading words;
- chunk ids are deterministic given the same input and article id.
"""

import re

from rag_agent.schemas import Chunk

_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?\s*")
_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def _sentences(paragraph: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(paragraph) if m.group(0).strip()]


def _word_windows(
    words: list[str], size: int, overlap: int, chunks: list[Chunk], article_id: str
) -> None:
    """Split ``words`` into fixed windows of ``size`` stepping ``size - overlap``."""
    step = size - overlap
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if not window:
            break
        text = " ".join(window)
        chunks.append(
            Chunk(
                chunk_id=f"{article_id}#c{len(chunks):03d}",
                article_id=article_id,
                text=text,
                token_count=len(window),
            )
        )
        if start + size >= len(words):
            break


def _append_chunk(chunks: list[Chunk], article_id: str, text: str) -> None:
    chunks.append(
        Chunk(
            chunk_id=f"{article_id}#c{len(chunks):03d}",
            article_id=article_id,
            text=text,
            token_count=len(text.split()),
        )
    )


def _split_paragraph(
    paragraph: str, size: int, overlap: int, article_id: str, chunks: list[Chunk]
) -> None:
    """Split one over-long paragraph: sentences first, words as fallback."""
    current: list[str] = []
    current_tokens = 0
    for sentence in _sentences(paragraph):
        s_tokens = len(sentence.split())
        if s_tokens > size:
            # Sentence alone exceeds the budget: flush what we have, then fall
            # back to hard word windows for the sentence itself.
            if current:
                _append_chunk(chunks, article_id, " ".join(current))
                current, current_tokens = [], 0
            _word_windows(sentence.split(), size, overlap, chunks, article_id)
            continue
        if current and current_tokens + s_tokens > size:
            _append_chunk(chunks, article_id, " ".join(current))
            current, current_tokens = [], 0
        current.append(sentence)
        current_tokens += s_tokens
    if current:
        _append_chunk(chunks, article_id, " ".join(current))


def chunk_by_size(text: str, article_id: str, size: int, overlap: int) -> list[Chunk]:
    """Chunk ``text`` into at most ``size``-token chunks with word overlap.

    Args:
        text: Article (or passage) text.
        article_id: Deterministic id stamped on every chunk and used as the
            chunk-id prefix (``{article_id}#cNNN``).
        size: Maximum tokens (whitespace-split words) per chunk.
        overlap: Tokens shared between consecutive word-level splits.

    Returns:
        Chunks with deterministic ids; every chunk carries ``article_id``.

    Raises:
        ValueError: If ``size`` or ``overlap`` are invalid.
    """
    if size < 1:
        raise ValueError("size must be >= 1")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current_paragraphs: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        p_tokens = len(paragraph.split())
        if p_tokens > size:
            # Paragraph does not fit whole anywhere: flush the pending block,
            # then recursively split the paragraph itself.
            if current_paragraphs:
                _append_chunk(chunks, article_id, "\n\n".join(current_paragraphs))
                current_paragraphs, current_tokens = [], 0
            _split_paragraph(paragraph, size, overlap, article_id, chunks)
            continue
        if current_paragraphs and current_tokens + p_tokens > size:
            _append_chunk(chunks, article_id, "\n\n".join(current_paragraphs))
            current_paragraphs, current_tokens = [], 0
        current_paragraphs.append(paragraph)
        current_tokens += p_tokens
    if current_paragraphs:
        _append_chunk(chunks, article_id, "\n\n".join(current_paragraphs))
    return chunks
