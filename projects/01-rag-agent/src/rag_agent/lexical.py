"""Deterministic word-matching (lexical) retrievers and rank fusion.

The seeded uniform-random baseline (:func:`rag_agent.evaluate.random_ranks`)
quantifies chance, but a client rightly asks "why not plain keyword search?"
before buying embeddings. This module implements that comparator offline:
tokenise the question (lowercase alphanumeric tokens, stopwords removed),
score every chunk, rank by score, and read off the rank of the first relevant
chunk. No models, no network, no new dependencies — the same committed
chunk store the embeddings index uses (:mod:`rag_agent.index`).

Two retrievers:
- :func:`lexical_ranks` — the original token-overlap floor (kept for the
  published chunk-size sweep continuity).
- :func:`bm25_ranking` — Robertson-Zaragoza BM25 (k1=1.2, b=0.75), the
  modern lexical baseline and one RRF fusion arm (external audit pass 4:
  hybrid sparse+dense is the production default; dense-only is dated).

:func:`reciprocal_rank_fusion` combines ranked chunk-id lists with RRF
(k=60, the no-tuning default from Cormack et al. 2009).

Ties are broken by ``chunk_id`` so rankings are fully deterministic.
"""

import math
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


class Bm25Index:
    """In-memory BM25 over the chunk store (Robertson-Zaragoza).

    k1=1.2 / b=0.75 are the textbook defaults — the point of the arm is the
    comparison against dense and RRF, not BM25 hyper-tuning. Deterministic:
    ties break by chunk_id, and the corpus statistics are fixed per chunk set.
    """

    def __init__(self, chunks: Sequence[ChunkRecord], k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._chunks = list(chunks)
        self._doc_tokens = [tokenize(c.text) for c in self._chunks]
        self._doc_ids = [c.chunk_id for c in self._chunks]
        df: dict[str, int] = {}
        for toks in self._doc_tokens:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        n = len(self._doc_tokens)
        self._avgdl = sum(len(d) for d in self._doc_tokens) / max(n, 1)
        # Robertson idf with the +1 floor: never negative on high-df terms.
        self._idf = {t: math.log(1.0 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def ranking(self, query: str) -> list[str]:
        """All chunk ids ranked by BM25 score (deterministic tie-break)."""
        q_tokens = tokenize(query)
        if not q_tokens:
            return list(self._doc_ids)
        scored = []
        for i, toks in enumerate(self._doc_tokens):
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            dl = len(toks)
            score = 0.0
            for t in q_tokens:
                f = tf.get(t, 0)
                if f == 0:
                    continue
                idf = self._idf.get(t, 0.0)
                score += (
                    idf
                    * (f * (self.k1 + 1))
                    / (f + self.k1 * (1 - self.b + self.b * dl / self._avgdl))
                )
            scored.append((-score, self._doc_ids[i]))
        scored.sort()
        return [cid for _, cid in scored]


def reciprocal_rank_fusion(rank_lists: Sequence[Sequence[str]], k: int = 60) -> list[str]:
    """RRF over ranked chunk-id lists: score = Σ 1/(k + rank), ties by id.

    k=60 is the literature's no-tuning default (Cormack, Clarke & Büttcher
    2009) — deliberately not swept, so the arm answers "is fusion worth it
    out of the box", not "what is the best possible fusion".
    """
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for pos, cid in enumerate(lst):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + pos + 1)
    return sorted(scores, key=lambda cid: (-scores[cid], cid))


def ndcg_at_k(
    ranked_article_ids: Sequence[str], relevant_article_ids: Sequence[str], k: int
) -> float:
    """nDCG@k with binary gains for one ranked list (relevant article = 1).

    The ranked list is chunk-level but relevance is article-level, so gains
    are computed over the first-occurrence article sequence — each article
    contributes once (an article's five chunks are one relevant item, not
    five). Without the dedupe the ratio can exceed 1, which is how the
    initial implementation gave itself away. Ideal DCG assumes one relevant
    item per rank slot up to min(#relevant, k); per-chunk grades are
    unavailable because the eval set labels whole articles.
    """
    seen: set[str] = set()
    deduped: list[str] = []
    for aid in ranked_article_ids:
        if aid not in seen:
            seen.add(aid)
            deduped.append(aid)
    relevant = set(relevant_article_ids)
    dcg = 0.0
    for pos, aid in enumerate(deduped[:k]):
        if aid in relevant:
            dcg += 1.0 / math.log2(pos + 2)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0
