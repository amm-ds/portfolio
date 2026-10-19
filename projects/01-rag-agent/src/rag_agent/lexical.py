"""Deterministic word-matching (lexical) retriever — the fair naive floor.

The seeded uniform-random baseline (:func:`rag_agent.evaluate.random_ranks`)
quantifies chance, but a client rightly asks "why not plain keyword search?"
before buying embeddings. This module implements that comparator offline:
tokenise the question (lowercase alphanumeric tokens, stopwords removed),
score every chunk by token-overlap count, rank by score, and read off the
rank of the first relevant chunk. No models, no network — the same committed
chunk store the embeddings index uses (:mod:`rag_agent.index`).

Ties are broken by ``chunk_id`` so the ranking is fully deterministic.
"""

import re
from collections.abc import Sequence

from rag_agent.index import ChunkRecord
from rag_agent.schemas import EvalQuestion

# Compact English stopword list (deterministic, no NLTK dependency). The
# ranker only needs the common function words; content words carry the signal.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "their",
        "there",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens with stopwords removed."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def lexical_ranks(
    chunks: Sequence[ChunkRecord],
    questions: Sequence[EvalQuestion],
    top_k: int = 10,
) -> list[int | None]:
    """1-based rank of the first relevant chunk under word-match ranking.

    Each chunk scores the count of *distinct* question tokens it contains;
    chunks are ranked by (-score, chunk_id) — deterministic on ties. Returns
    the first-relevant rank within the top ``top_k`` per question, or None.
    """
    chunk_tokens = [set(tokenize(c.text)) for c in chunks]
    chunk_ids = [c.chunk_id for c in chunks]
    ranks: list[int | None] = []
    for question in questions:
        query_tokens = set(tokenize(question.question))
        if not query_tokens:
            ranks.append(None)
            continue
        scored = [
            (-len(query_tokens & tokens), chunk_ids[i], i) for i, tokens in enumerate(chunk_tokens)
        ]
        scored.sort()
        if -scored[0][0] == 0:
            ranks.append(None)  # no token overlap anywhere: word-match found nothing
            continue
        relevant = set(question.relevant_article_ids)
        rank = next(
            (
                pos + 1
                for pos, (_, _, i) in enumerate(scored[:top_k])
                if chunks[i].article_id in relevant
            ),
            None,
        )
        ranks.append(rank)
    return ranks
