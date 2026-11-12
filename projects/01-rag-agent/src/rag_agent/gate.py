"""Inference-time evidence gate (R6): refuse before generating when the
retrieved evidence cannot plausibly answer the question.

A tuning-calibrated hard abstention gate plus a continuous evidence signal,
built ONLY from inference-observable inputs — never gold question metadata
(``relevant_article_ids`` stays out of this path; using it would be label
leakage). Shared by the evaluation loop and the chat CLI so both make
decisions from the same information.
"""

import re
import unicodedata
from dataclasses import dataclass

from portfolio_core.logging import get_logger

logger = get_logger("rag_agent.gate")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "did",
    "does",
    "do",
    "had",
    "have",
    "their",
    "there",
    "than",
    "then",
    "into",
    "about",
    "after",
    "before",
    "between",
    "during",
    "its",
    "this",
    "these",
    "those",
    "over",
    "under",
    "more",
    "most",
    "many",
    "much",
    "can",
    "could",
}

_WORD_RE = re.compile(r"[a-z0-9]+")


def content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower())} - _STOPWORDS


@dataclass(frozen=True)
class GateConfig:
    """Thresholds selected on tuning-set diagnostics only (never the frozen
    stress sets). ``min_coverage``/``min_max_similarity`` below → refusal."""

    min_coverage: float = 0.34
    min_max_similarity: float = 0.25


@dataclass(frozen=True)
class GateDecision:
    refuses: bool
    coverage: float
    max_similarity: float
    evidence_score: float  # continuous signal, traces only — not user-facing


def assess(question: str, chunk_texts: list[str], config: GateConfig | None = None) -> GateDecision:
    """Score evidence against a question; refuse when it cannot plausibly answer.

    ``coverage`` = share of question content words present in the union of
    chunk texts; ``max_similarity`` = the best single-chunk content overlap.
    Both are inference-observable; the decision uses only them.
    """
    cfg = config or GateConfig()
    q_words = content_words(question)
    if not q_words or not chunk_texts:
        return GateDecision(refuses=True, coverage=0.0, max_similarity=0.0, evidence_score=0.0)
    union: set[str] = set()
    max_sim = 0.0
    for text in chunk_texts:
        words = content_words(text)
        union |= words
        if words:
            max_sim = max(max_sim, len(q_words & words) / len(q_words))
    coverage = len(q_words & union) / len(q_words)
    # continuous evidence signal for traces (not a calibrated probability)
    evidence_score = round(0.6 * coverage + 0.4 * max_sim, 4)
    refuses = coverage < cfg.min_coverage or max_sim < cfg.min_max_similarity
    return GateDecision(refuses, round(coverage, 4), round(max_sim, 4), evidence_score)


def normalize(text: str) -> str:
    """NFKC normalization — Unicode composition equivalence only (does not
    equate a with ä); whitespace collapsed for robust span matching."""
    collapsed = " ".join(text.split())
    return unicodedata.normalize("NFKC", collapsed).lower()
