"""R4: retrieval baseline — dense (MiniLM) vs BM25 on the committed sealed set.

Re-runs the two pure-retrieval arms through the project's own machinery
(:class:`rag_agent.lexical.Bm25Index`, the committed FAISS index via
:class:`rag_agent.index.Retriever`, :func:`rag_agent.evaluate.load_heldout_questions`)
and reports recall@5 with a Wilson 95% interval per retriever, plus recall@10
and MRR@5 for context. Retrieval-only: no LLM calls, no reranker.

Identity check: the point estimates must match the committed
``reports/sealed_retrieval.json`` arms (dense 0.9762 / bm25 0.9524) before the
new intervals are trusted.

Output: NEW files under ``reports/retrieval_baseline/`` only; no committed
record is touched.

    uv run python scripts/retrieval_baseline.py
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger
from rag_agent.cli import load_config
from rag_agent.corpus import load_corpus
from rag_agent.evaluate import (
    first_relevant_rank_ids,
    load_heldout_questions,
    mrr_at_5,
    recall_at_k,
)
from rag_agent.index import Retriever, SentenceTransformerEmbedder, chunk_articles
from rag_agent.lexical import Bm25Index

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def main() -> int:
    config = load_config()
    articles = load_corpus(config)
    heldout = load_heldout_questions(config, articles)
    answerable = [q for q in heldout if q.relevant_article_ids]

    size = min(config.chunk_sizes)
    chunks = chunk_articles(articles, size=size, overlap=config.chunk_overlap)
    chunk_by_id = {c.chunk_id: c for c in chunks}
    bm25 = Bm25Index(chunks)
    dense = Retriever.from_index_dir(
        config, config.index_path(size), SentenceTransformerEmbedder(config.embedding_model), None
    )

    per_arm: dict[str, dict[str, Any]] = {}
    for arm in ("dense", "bm25"):
        ranks: list[int | None] = []
        hits5 = 0
        for q in answerable:
            relevant = set(q.relevant_article_ids)
            if arm == "dense":
                ranked = [c.article_id for c in dense.search(q.question, top_k=10)]
            else:
                ids = bm25.ranking(q.question)[:10]
                ranked = [chunk_by_id[cid].article_id for cid in ids]
            rank = first_relevant_rank_ids(ranked, relevant)
            ranks.append(rank)
            if rank is not None and rank <= 5:
                hits5 += 1
        n = len(answerable)
        per_arm[arm] = {
            "recall_at_5": recall_at_k(ranks, 5),
            "recall_at_5_wilson95": list(wilson(hits5, n)),
            "recall_at_10": recall_at_k(ranks, 10),
            "mrr_at_5": mrr_at_5(ranks),
            "n_answerable": n,
        }
        logger.info(
            "%s recall@5 %.4f %s (n=%d)",
            arm,
            per_arm[arm]["recall_at_5"],
            wilson(hits5, n),
            n,
        )

    committed = json.loads((ROOT / "reports" / "sealed_retrieval.json").read_text())
    verification = {}
    for arm in ("dense", "bm25"):
        expected = committed["arms"][arm]["recall_at_5"]
        got = per_arm[arm]["recall_at_5"]
        verification[arm] = {
            "recomputed": got,
            "committed": expected,
            "matches": abs(got - expected) < 5e-4,
        }
        if not verification[arm]["matches"]:
            raise ValueError(f"{arm} recall drift: {got} != committed {expected}")

    report = {
        "schema_version": "retrieval-baseline-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "set": "sealed held-out (committed), answerable questions only",
        "n_questions_total": len(heldout),
        "method": "retrieval-only recompute; dense = committed FAISS IndexFlatIP (MiniLM, "
        "rerank off); BM25 k1=1.2 b=0.75 over the same 200-token chunks; "
        "Wilson score interval",
        "arms": per_arm,
        "verification_against_committed_sealed_retrieval": verification,
        "reading": (
            "BM25 recall@5 sits within a few points of dense on this corpus; "
            "the gap is far inside both intervals - consistent with the "
            "committed fusion read that hybrid arms do not clear the gate."
        ),
    }
    out_dir = ROOT / "reports" / "retrieval_baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    d, b = per_arm["dense"], per_arm["bm25"]
    lines = [
        "# R4 retrieval baseline — dense vs BM25 on the sealed set",
        "",
        f"Generated: {report['generated_at']} · n = {d['n_answerable']} answerable sealed "
        f"questions (of {len(heldout)} total) · retrieval-only, rerank off.",
        "",
        "| retriever | recall@5 | Wilson 95% | recall@10 | MRR@5 |",
        "|---|---|---|---|---|",
        f"| dense (MiniLM, committed FAISS) | {d['recall_at_5']:.4f} "
        f"| [{d['recall_at_5_wilson95'][0]:.4f}, {d['recall_at_5_wilson95'][1]:.4f}] "
        f"| {d['recall_at_10']:.4f} | {d['mrr_at_5']:.4f} |",
        f"| BM25 (k1=1.2, b=0.75) | {b['recall_at_5']:.4f} "
        f"| [{b['recall_at_5_wilson95'][0]:.4f}, {b['recall_at_5_wilson95'][1]:.4f}] "
        f"| {b['recall_at_10']:.4f} | {b['mrr_at_5']:.4f} |",
        "",
        "Point estimates recomputed and verified against the committed "
        "`reports/sealed_retrieval.json` arms (dense 0.9762, BM25 0.9524). "
        "New files only; no committed record touched.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    logger.info("wrote %s", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
