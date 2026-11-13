"""Paragraph-aware recursive chunking — with optional structure awareness (R7).

Chunks are packed from whole paragraphs first; paragraphs longer than the size
budget are split at sentence boundaries, and pathologically long sentences are
split at word boundaries with a word-level overlap. Guarantees (unit-tested):

- every chunk has at most ``size`` whitespace-delimited tokens (body only —
  the R7 title prefix is metadata, not counted against the budget);
- consecutive word-level splits share exactly ``overlap`` trailing/leading words;
- chunk ids are deterministic given the same input and article id;
- R7: ``chunk_by_structure`` prefixes every chunk with the article title (the
  corpus carries no ``==`` section markers — verified across all 593 articles)
  and records body character offsets into the source text as provenance.
"""

import re

from rag_agent.schemas import Chunk

_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?\s*")
_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def _sentences(paragraph: str) -> list[str]:
    return [m.group(0).strip() for m in _SENTENCE_RE.finditer(paragraph) if m.group(0).strip()]


def _word_windows(
    words: list[str],
    size: int,
    overlap: int,
    chunks: list[tuple[str, int]],
    article_id: str,
    base_offset: int,
) -> None:
    """Split ``words`` into fixed windows of ``size`` stepping ``size - overlap``."""
    step = size - overlap
    # Character offsets for word windows are approximate (whitespace-joined):
    # provenance anchors at the paragraph start plus the joined prefix length.
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if not window:
            break
        text = " ".join(window)
        prefix = " ".join(words[:start])
        offset = base_offset + (len(prefix) + 1 if prefix else 0)
        chunks.append((text, offset))
        if start + size >= len(words):
            break


def _append_chunk(chunks: list[tuple[str, int]], article_id: str, text: str, offset: int) -> None:
    chunks.append((text, offset))


def _split_paragraph(
    paragraph: str,
    size: int,
    overlap: int,
    article_id: str,
    chunks: list[tuple[str, int]],
    base_offset: int,
) -> None:
    """Split one over-long paragraph: sentences first, words as fallback."""
    current: list[str] = []
    current_tokens = 0
    current_offset = base_offset
    cursor = base_offset
    for sentence in _sentences(paragraph):
        s_tokens = len(sentence.split())
        s_offset = paragraph.find(sentence, cursor - base_offset) + base_offset
        if s_tokens > size:
            # Sentence alone exceeds the budget: flush what we have, then fall
            # back to hard word windows for the sentence itself.
            if current:
                body = " ".join(current)
                _append_chunk(chunks, article_id, body, current_offset)
                current, current_tokens = [], 0
            _word_windows(sentence.split(), size, overlap, chunks, article_id, s_offset)
            cursor = s_offset + len(sentence)
            continue
        if current and current_tokens + s_tokens > size:
            body = " ".join(current)
            _append_chunk(chunks, article_id, body, current_offset)
            current, current_tokens = [], 0
        if not current:
            current_offset = s_offset
        current.append(sentence)
        current_tokens += s_tokens
        cursor = s_offset + len(sentence)
    if current:
        body = " ".join(current)
        _append_chunk(chunks, article_id, body, current_offset)


def _pack(text: str, size: int, overlap: int, article_id: str) -> list[tuple[str, int]]:
    """Pack paragraphs into (body, char_offset) pairs. Shared by both modes."""
    if size < 1:
        raise ValueError("size must be >= 1")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    # Paragraph segments lie BETWEEN the separator matches — keep offsets.
    segments: list[tuple[str, int]] = []
    cursor = 0
    for match in _PARAGRAPH_RE.finditer(text):
        segments.append((text[cursor : match.start()], cursor))
        cursor = match.end()
    segments.append((text[cursor:], cursor))

    chunks: list[tuple[str, int]] = []
    current_paragraphs: list[str] = []
    current_tokens = 0
    current_offset = 0
    for segment, seg_offset in segments:
        paragraph = segment.strip()
        if not paragraph:
            continue
        p_tokens = len(paragraph.split())
        if p_tokens > size:
            # Paragraph does not fit whole anywhere: flush the pending block,
            # then recursively split the paragraph itself.
            if current_paragraphs:
                _append_chunk(chunks, article_id, "\n\n".join(current_paragraphs), current_offset)
                current_paragraphs, current_tokens = [], 0
            lead = len(segment) - len(segment.lstrip())
            _split_paragraph(paragraph, size, overlap, article_id, chunks, seg_offset + lead)
            continue
        if current_paragraphs and current_tokens + p_tokens > size:
            _append_chunk(chunks, article_id, "\n\n".join(current_paragraphs), current_offset)
            current_paragraphs, current_tokens = [], 0
        if not current_paragraphs:
            current_offset = seg_offset + (len(segment) - len(segment.lstrip()))
        current_paragraphs.append(paragraph)
        current_tokens += p_tokens
    if current_paragraphs:
        _append_chunk(chunks, article_id, "\n\n".join(current_paragraphs), current_offset)
    return chunks


def _materialize(packed: list[tuple[str, int]], article_id: str, title_prefix: str) -> list[Chunk]:
    out: list[Chunk] = []
    for body, offset in packed:
        text = f"{title_prefix}{body}" if title_prefix else body
        out.append(
            Chunk(
                chunk_id=f"{article_id}#c{len(out):03d}",
                article_id=article_id,
                text=text,
                token_count=len(body.split()),
                char_start=offset,
                char_end=offset + len(body),
            )
        )
    return out


def chunk_by_size(text: str, article_id: str, size: int, overlap: int) -> list[Chunk]:
    """Chunk ``text`` into at most ``size``-token chunks with word overlap (R0)."""
    return _materialize(_pack(text, size, overlap, article_id), article_id, "")


def chunk_by_structure(
    text: str, article_id: str, title: str, size: int, overlap: int
) -> list[Chunk]:
    """R7 structure-aware chunking: title-prefixed, offset-provenanced (R1).

    The corpus has no section markers (verified across all 593 articles), so
    "structure" here means the article title anchors every chunk — entity
    questions retrieve far better when the entity name is in the chunk text —
    plus body character offsets for provenance. Ids stay deterministic.
    """
    packed = _pack(text, size, overlap, article_id)
    return _materialize(packed, article_id, f"{title}\n\n")
