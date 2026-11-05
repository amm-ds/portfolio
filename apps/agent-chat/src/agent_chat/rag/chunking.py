"""Document loading and chunking for the ingest pipeline.

Chunking is paragraph-first (markdown/txt documents read naturally at
paragraph boundaries), with sentence- then hard-splitting for oversized
paragraphs, and a small overlap so sentences at chunk edges stay retrievable.
Fully deterministic: same document, same chunks.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = frozenset({".md", ".txt"})

_SENTENCE_RE = re.compile(r"(?<=[.!?;])\s+")

DEFAULT_MAX_CHARS = 500
DEFAULT_OVERLAP = 50


@dataclass(frozen=True)
class Chunk:
    """One searchable unit of a document."""

    source: str
    index: int
    text: str


def load_documents(paths: Iterable[Path]) -> list[tuple[str, str]]:
    """Read ``.md``/``.txt`` files as (source, text) pairs.

    Directories are walked recursively; other suffixes are skipped with a
    warning-free ignore (the ingest report counts only what was read).
    """
    documents: list[tuple[str, str]] = []
    for path in paths:
        if path.is_dir():
            documents.extend(load_documents(sorted(p for p in path.rglob("*") if p.is_file())))
        elif path.suffix.lower() in SUPPORTED_SUFFIXES and path.is_file():
            documents.append((str(path), path.read_text(encoding="utf-8")))
    return documents


def _split_paragraph(text: str, max_chars: int) -> list[str]:
    """Split one paragraph at sentence boundaries, then hard, until it fits."""
    pieces = [p for p in _SENTENCE_RE.split(text) if p]
    if len(pieces) <= 1:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
    units: list[str] = []
    for piece in pieces:
        if len(piece) <= max_chars:
            units.append(piece)
        else:
            units.extend(piece[i : i + max_chars] for i in range(0, len(piece), max_chars))
    return units


def chunk_text(
    source: str,
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Split ``text`` into overlapping chunks attributed to ``source``."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    flat: list[str] = []
    for paragraph in paragraphs:
        flat.extend(_split_paragraph(paragraph, max_chars))

    texts: list[str] = []
    current = ""
    for unit in flat:
        candidate = f"{current} {unit}".strip() if current else unit
        if current and len(candidate) > max_chars:
            texts.append(current)
            tail = current[-overlap:] if overlap > 0 else ""
            current = f"{tail} {unit}".strip()
        else:
            current = candidate
    if current:
        texts.append(current)
    return [Chunk(source=source, index=i, text=c) for i, c in enumerate(texts)]
