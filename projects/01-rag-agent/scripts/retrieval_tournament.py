"""R7 retrieval-only tournament: measure before committing (no generation, no LLM judging).

Arms (R7 plan §4.2), all against the champion config's chunk size:

    R0  current chunking + MiniLM + exact FAISS + current cross-encoder   (control)
    R1  structure-aware chunking (title-prefixed, offset-provenanced) + rest of R0
    R2  R0 chunking + Qwen3-Embedding-0.6B (local Ollama)
    R3  best chunking x best dense embedding (derived from R1/R2)
    R4  R3 + BM25 candidates fused with RRF(k=60)
    R5  R4 x {current cross-encoder, Qwen3-Reranker-0.6B}

Metrics per arm (tuning set; development reads of A/B optional): gold-evidence
recall@5/10/20, nDCG@10, MRR@10, article coverage in the final context,
unanswerable false-evidence proxy, estimated prompt tokens, retrieval p50/p95,
index size. Promotion gate: >= +5pts recall@10 vs R0, no primary slice
regression > 2pts, prompt tokens <= +15%, p95 <= +25%.

Usage (from the project root, local models pulled):
    uv run python scripts/retrieval_tournament.py
    # [--out reports/retrieval_tournament]
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rag_agent.chunking import chunk_by_size, chunk_by_structure
from rag_agent.config import RAGConfig
from rag_agent.corpus import load_corpus
from rag_agent.evaluate import (
    first_relevant_rank_ids,
    load_questions,
)
from rag_agent.index import Retriever, SentenceTransformerEmbedder, build_index
from rag_agent.lexical import Bm25Index, reciprocal_rank_fusion
from rag_agent.local_models import HfQwenReranker, OllamaEmbedder, ollama_available
from rag_agent.schemas import Article, EvalQuestion

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Arm:
    name: str
    chunk_mode: str  # "size" | "structure"
    embed_slug: str  # "minilm" | "qwen3e"
    fusion: bool
    rerank_slug: str  # "none" | "msmarco" | "qwen3r"


def _chunks_for(arm: Arm, articles: list[Article], size: int, overlap: int) -> list[Any]:
    from rag_agent.index import ChunkRecord

    chunks: list[Any] = []
    for article in articles:
        if arm.chunk_mode == "structure":
            cut = chunk_by_structure(article.text, article.article_id, article.title, size, overlap)
        else:
            cut = chunk_by_size(article.text, article.article_id, size, overlap)
        chunks.extend(
            ChunkRecord(
                chunk_id=c.chunk_id,
                article_id=c.article_id,
                text=c.text,
                token_count=c.token_count,
                char_start=c.char_start,
                char_end=c.char_end,
                title=article.title,
                topic=article.topic,
            )
            for c in cut
        )
    return chunks


def _embed_fn(slug: str) -> Callable[[Sequence[str]], np.ndarray]:
    if slug == "minilm":
        return SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
    if slug == "qwen3e":
        return OllamaEmbedder("qwen3-embedding:0.6b")
    raise ValueError(slug)


def _rerank_fn(slug: str) -> Callable[[str, Sequence[str]], np.ndarray] | None:
    if slug == "none":
        return None
    if slug == "msmarco":
        from rag_agent.index import CrossEncoderReranker

        return CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")
    if slug == "qwen3r":
        return HfQwenReranker()
    raise ValueError(slug)


def run_arm(
    arm: Arm,
    questions: list[EvalQuestion],
    articles: list[Article],
    config: RAGConfig,
    index_root: Path,
) -> dict[str, Any]:
    size = config.retrieval_best.chunk_size if config.retrieval_best else min(config.chunk_sizes)
    overlap = config.chunk_overlap
    index_dir = index_root / f"tourn_{arm.name}_{arm.chunk_mode}_{arm.embed_slug}"
    chunks = _chunks_for(arm, articles, size, overlap)
    if not (index_dir / "faiss.index").exists():
        index_dir.parent.mkdir(parents=True, exist_ok=True)
        build_index(chunks, _embed_fn(arm.embed_slug), index_dir, description=arm.name)
    embedder = _embed_fn(arm.embed_slug)
    retriever = Retriever.from_index_dir(config, index_dir, embedder, None)
    bm25 = Bm25Index(chunks) if arm.fusion else None
    chunk_by_id = {c.chunk_id: c for c in chunks}
    rerank = _rerank_fn(arm.rerank_slug)
    k = config.retrieval_best.top_k if config.retrieval_best else config.top_k

    ranks: list[int | None] = []
    ndcgs: list[float] = []
    coverage: list[float] = []
    abstain_overlap: list[float] = []
    prompt_tokens: list[int] = []
    latencies: list[float] = []
    rr_at: dict[int, list[float]] = {5: [], 10: [], 20: []}

    stop = {
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
    }

    def words(text: str) -> set[str]:
        return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split()} - stop

    for q in questions:
        relevant = set(q.relevant_article_ids)
        start = time.perf_counter()
        dense = retriever.search(q.question, top_k=20)
        ranked: list[str] = [c.chunk_id for c in dense]
        if bm25 is not None:
            bm_ids = bm25.ranking(q.question)[:20]
            ranked = reciprocal_rank_fusion([ranked, bm_ids])[:20]
        cand = [chunk_by_id[cid] for cid in ranked if cid in chunk_by_id]
        if rerank is not None and cand:
            scores = rerank(q.question, [c.text for c in cand])
            order = np.argsort(-scores)
            cand = [cand[int(i)] for i in order]
        top = cand[:k]
        latencies.append(time.perf_counter() - start)

        # Recall@k / nDCG / MRR measure the CANDIDATE list (top-20), not the
        # final truncated context — otherwise every recall@k is identical.
        cand_articles = [c.article_id for c in cand[:20]]
        rank = first_relevant_rank_ids(cand_articles, relevant)
        ranks.append(rank)
        for kk in rr_at:
            rr_at[kk].append(1.0 if (rank is not None and rank <= kk) else 0.0)
        # nDCG@10 with binary gains counted ONCE per relevant article (several
        # chunks can share an article — duplicate gains inflated this past 1.0).
        seen: set[str] = set()
        dcg = 0.0
        for i, aid in enumerate(cand_articles[:10]):
            if aid in relevant and aid not in seen:
                seen.add(aid)
                dcg += 1.0 / np.log2(i + 2)
        ideal = min(len(relevant), 10)
        ndcgs.append(dcg / sum(1.0 / np.log2(i + 2) for i in range(ideal)) if ideal else 0.0)
        ranked_articles = [c.article_id for c in top]
        coverage.append(1.0 if any(aid in relevant for aid in ranked_articles) else 0.0)
        prompt_tokens.append(sum(c.token_count for c in top))
        if q.expected_behavior == "abstain" and top:
            qw = words(q.question)
            best = max(len(qw & words(c.text)) / len(qw) if qw else 0.0 for c in top)
            abstain_overlap.append(best)

    def mean(xs: list[float]) -> float:
        return float(sum(xs) / len(xs)) if xs else 0.0

    mrr10 = mean([1.0 / r if (r is not None and r <= 10) else 0.0 for r in ranks])
    return {
        "arm": arm.name,
        "config": {
            "chunk_mode": arm.chunk_mode,
            "embedding": arm.embed_slug,
            "fusion_rrf": arm.fusion,
            "reranker": arm.rerank_slug,
            "chunk_size": size,
            "top_k": k,
        },
        "n_questions": len(questions),
        "recall@5": mean(rr_at[5]),
        "recall@10": mean(rr_at[10]),
        "recall@20": mean(rr_at[20]),
        "ndcg@10": mean(ndcgs),
        "mrr@10": mrr10,
        "article_coverage@context": mean(coverage),
        "unanswerable_false_evidence_proxy": mean(abstain_overlap),
        "est_prompt_tokens_mean": mean([float(t) for t in prompt_tokens]),
        "retrieval_p50_s": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "retrieval_p95_s": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "n_index_chunks": len(chunks),
    }


def promotion_verdict(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {r["arm"]: r for r in results}
    r0 = by_name["R0"]
    verdicts = {}
    for name, r in by_name.items():
        if name == "R0":
            continue
        gain10 = r["recall@10"] - r0["recall@10"]
        token_delta = (r["est_prompt_tokens_mean"] - r0["est_prompt_tokens_mean"]) / max(
            r0["est_prompt_tokens_mean"], 1.0
        )
        p95_delta = (r["retrieval_p95_s"] - r0["retrieval_p95_s"]) / max(
            r0["retrieval_p95_s"], 1e-9
        )
        verdicts[name] = {
            "delta_recall@10": round(gain10, 4),
            "prompt_token_growth": round(token_delta, 4),
            "p95_growth": None if not np.isfinite(p95_delta) else round(p95_delta, 4),
            "clears_promotion_gate": bool(
                gain10 >= 0.05
                and token_delta <= 0.15
                and (p95_delta <= 0.25 or r0["retrieval_p95_s"] < 0.05)
            ),
        }
    return verdicts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "retrieval_tournament")
    parser.add_argument("--skip-ollama", action="store_true", help="run local-only arms (MiniLM)")
    args = parser.parse_args()

    has_ollama = ollama_available() and not args.skip_ollama
    config = RAGConfig()
    articles = load_corpus(config)
    questions = load_questions(config, articles)

    arms = [
        Arm("R0", "size", "minilm", fusion=False, rerank_slug="msmarco"),
        Arm("R1", "structure", "minilm", fusion=False, rerank_slug="msmarco"),
    ]
    if has_ollama:
        arms += [
            Arm("R2", "size", "qwen3e", fusion=False, rerank_slug="msmarco"),
            Arm("R5a", "size", "minilm", fusion=True, rerank_slug="msmarco"),
            Arm("R5b", "size", "minilm", fusion=True, rerank_slug="qwen3r"),
        ]
    else:
        arms.append(Arm("R5a", "size", "minilm", fusion=True, rerank_slug="msmarco"))

    results = [run_arm(a, questions, articles, config, config.index_dir) for a in arms]
    report = {
        "sets": ["tuning"],
        "n_questions": len(questions),
        "ollama_arms_included": has_ollama,
        "promotion_gate": promotion_verdict(results),
        "arms": results,
        "note": (
            "retrieval-only tournament: no generation, no LLM judging; Ollama "
            "arms are local ($0). Gate: >= +5pts recall@10 vs R0, tokens <= +15%, "
            "p95 <= +25%. Slice regressions are audited before promotion."
        ),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "results.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["promotion_gate"], indent=2))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
