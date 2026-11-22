"""Measure retrieval quality on dev splits or final_v3 — steps 2, 3 and 5 of
the 20261122-rag-execution-plan handoff (Revision 1).

Retrieval-only: no LLM generation, no hosted calls. Every model loads from the
local HF cache (HF_HUB_OFFLINE=1) or from Ollama on 127.0.0.1; the destination
host of every httpx request is captured and recorded per run, and any host
outside {localhost, 127.0.0.1} stops the run.

Splits (``--split``):
- ``dev_v1``  — the 20 tuning questions frozen in ``data/dev_v1.sha256.json``.
- ``dev_40`` / ``dev_65`` — deterministic superset-extension of dev_v1
  (seed 43 complement sampling per category to 24/8/8, then all 65).
- ``final_v3`` — the sealed-quality set; its question file is read ONLY for
  this split (never before step 5).

Gold: dev splits resolve ``relevant_titles`` to corpus articles and count every
chunk of those articles as gold (article-level gold — the only faithful mapping
for tuning questions). ``final_v3`` carries exact ``gold_chunk_ids``.

Metrics (answerable questions only, matching the committed
``reports/sealed_retrieval.json`` practice): recall@5 with a Wilson 95%
interval, MRR@5, mean context tokens per query for the production top-3 slice
and for the measured top-5, and per-category slices. For ``final_v3`` abstain
rows, an absent-term-in-top-5 false-evidence diagnostic is recorded.

The pinned baseline (default, no ``--config``) is ``params.yaml
retrieval_best``: chunk 200 / overlap 40 (size mode), MiniLM embeddings,
top_k 3, rerank ON with ``cross-encoder/ms-marco-MiniLM-L-6-v2`` and
``rerank_multiplier 5``. Note the README's "reranks the top 5 x k": the code
fetches ``k * rerank_multiplier`` candidates; measurement ranks top_k=5
(25 candidates fetched, reranked to 5) while the production serving slice
stays top_k=3 — both token numbers are reported.

    HF_HUB_OFFLINE=1 uv run python scripts/measure_retrieval.py --split dev_v1
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from portfolio_core.logging import get_logger
from rag_agent.chunking import chunk_by_structure
from rag_agent.cli import load_config
from rag_agent.corpus import load_corpus
from rag_agent.index import (
    ChunkRecord,
    CrossEncoderReranker,
    Retriever,
    SentenceTransformerEmbedder,
    build_index,
    chunk_articles,
    load_index,
)
from rag_agent.runner import HostGrabber, config_hash, git_commit, git_dirty, sha256_file

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]

LOCAL_HOSTS = {"localhost", "127.0.0.1", None}
MEASURE_K = 5
GROW_SEED = 43
DEV40_TARGETS = {"single_hop": 24, "multi_hop": 8, "unanswerable": 8}
CATEGORY_ORDER = ("single_hop", "multi_hop", "unanswerable")

# Revision 1 binding: Qwen3-Reranker-0.6B is loaded WITHOUT trust_remote_code.
# Planning-time review of the cached snapshot e61197ed… found no remote-code
# files (no modeling_*.py/configuration_*.py — standard transformers config +
# safetensors + sentence-transformers modules), so a pinned-revision native
# load is sufficient. If the loader demands remote code, the arm is skipped
# and the reason recorded (offline rule prevents fetching any code).
QWEN_RERANKER = "Qwen/Qwen3-Reranker-0.6B"
QWEN_RERANKER_REVISION = "e61197ed45024b0ed8a2d74b80b4d909f1255473"
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
OLLAMA_EMBED_ENDPOINT = "http://127.0.0.1:11434/api/embed"


@dataclass
class SweepConfig:
    """One retrieval configuration; sweep files override these fields."""

    chunk_size: int = 200
    chunk_overlap: int = 40
    chunk_mode: str = "size"  # size | structure (title-prefixed; no section markers exist)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_kind: str = "local"  # local (HF cache) | ollama (127.0.0.1:11434)
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # "" = rerank off
    top_k: int = 3  # production serving slice (params.yaml retrieval_best)
    measure_k: int = MEASURE_K
    rerank_multiplier: int = 5
    name: str = "baseline"

    def candidates(self) -> int:
        return self.measure_k * self.rerank_multiplier


@dataclass
class Item:
    """One measured question with its gold definition."""

    question: str
    category: str
    behavior: str
    gold_article_ids: set[str] = field(default_factory=set)
    gold_chunk_ids: set[str] = field(default_factory=set)
    absent_terms: list[str] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> tuple[str, Path | None]:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", required=True, choices=["dev_v1", "dev_40", "dev_65", "final_v3"]
    )
    parser.add_argument("--config", type=Path, default=None, help="sweep config yaml")
    args = parser.parse_args(argv)
    return args.split, args.config


def load_sweep_config(path: Path | None) -> SweepConfig:
    if path is None:
        return SweepConfig()
    import yaml  # type: ignore[import-untyped]  # PyYAML has no stubs; same pattern as cli.py

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = SweepConfig()
    for key, value in data.items():
        if not hasattr(cfg, key):
            raise SystemExit(f"unknown sweep config key: {key}")
        setattr(cfg, key, value)
    if cfg.chunk_mode not in {"size", "structure"}:
        raise SystemExit(f"chunk_mode must be size|structure, got {cfg.chunk_mode!r}")
    if cfg.embedding_kind not in {"local", "ollama"}:
        raise SystemExit(f"embedding_kind must be local|ollama, got {cfg.embedding_kind!r}")
    return cfg


def is_pinned_baseline(cfg: SweepConfig) -> bool:
    return (
        cfg.chunk_size == 200
        and cfg.chunk_overlap == 40
        and cfg.chunk_mode == "size"
        and cfg.embedding_kind == "local"
        and cfg.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        and cfg.reranker_model == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        and cfg.top_k == 3
        and cfg.rerank_multiplier == 5
    )


class OllamaEmbedder:
    """Batch embedder over the local Ollama API (substitute for e5-small-v2).

    Revision-1-documented substitution: ``intfloat/e5-small-v2`` is absent from
    the local HF cache and downloads are prohibited by the local-only rule.
    """

    def __init__(self, model: str, endpoint: str = OLLAMA_EMBED_ENDPOINT, batch: int = 64) -> None:
        self.model = model
        self.endpoint = endpoint
        self.batch = batch

    def __call__(self, texts: list[str]) -> np.ndarray:
        import httpx

        out: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch):
            batch = texts[start : start + self.batch]
            resp = httpx.post(
                self.endpoint, json={"model": self.model, "input": batch}, timeout=600
            )
            resp.raise_for_status()
            vectors = np.asarray(resp.json()["embeddings"], dtype="float32")
            out.append(vectors)
        stacked: np.ndarray[Any, Any] = np.vstack(out)
        norms = np.linalg.norm(stacked, axis=1, keepdims=True) + 1e-12
        return np.asarray(stacked / norms, dtype="float32")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"OllamaEmbedder({self.model!r})"


class PrefixedQueryEmbedder:
    """BGE-style instruction prefix on queries only; passages embed bare."""

    def __init__(self, inner: SentenceTransformerEmbedder, prefix: str) -> None:
        self.inner = inner
        self.prefix = prefix

    def __call__(self, texts: list[str]) -> np.ndarray:
        return self.inner([self.prefix + t for t in texts])


class PinnedQwenReranker:
    """Qwen3-Reranker-0.6B at a pinned revision, NO trust_remote_code.

    Falls back to nothing on load failure: the caller records the skip.
    """

    def __init__(self, revision: str) -> None:
        from rag_agent.index import _guard_torch_threads  # shared guard
        from sentence_transformers import CrossEncoder

        _guard_torch_threads()
        self.model = CrossEncoder(
            QWEN_RERANKER,
            revision=revision,
            device="cpu",
            trust_remote_code=False,
        )

    def __call__(self, query: str, texts: list[str]) -> np.ndarray:
        pairs = [(query, text) for text in texts]
        return np.asarray(self.model.predict(pairs), dtype="float32")


def structure_records(articles: list[Any], size: int, overlap: int) -> list[ChunkRecord]:
    """Title-prefixed chunks (the corpus has no section markers to split on)."""
    records: list[ChunkRecord] = []
    for article in articles:
        for chunk in chunk_by_structure(
            article.text, article.article_id, article.title, size, overlap
        ):
            records.append(
                ChunkRecord(
                    chunk_id=chunk.chunk_id,
                    article_id=chunk.article_id,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    title=article.title,
                    topic=article.topic,
                )
            )
    return records


def build_or_load_sweep_index(cfg: SweepConfig, articles: list[Any]) -> Retriever:
    """Build (or reuse) the sweep index under the gitignored data/index/."""
    slug = f"{cfg.name}-{config_hash(cfg)[:12]}"
    out_dir = ROOT / "data" / "index" / "sweeps" / slug
    marker = out_dir / "sweep_marker.json"

    def build() -> None:
        if cfg.chunk_mode == "structure":
            chunks = structure_records(articles, cfg.chunk_size, cfg.chunk_overlap)
        else:
            chunks = chunk_articles(articles, size=cfg.chunk_size, overlap=cfg.chunk_overlap)
        embed_fn = make_embedder(cfg)
        build_index(chunks, embed_fn, out_dir, description=slug)
        marker.write_text(
            json.dumps({"config": asdict(cfg), "config_sha256": full_config_sha(cfg)}, indent=2)
            + "\n",
            encoding="utf-8",
        )

    if not (out_dir / "faiss.index").exists() or not marker.exists():
        build()
    else:
        recorded = json.loads(marker.read_text(encoding="utf-8"))["config_sha256"]
        if recorded != full_config_sha(cfg):
            raise SystemExit(f"sweep index {out_dir} was built with a different config")

    index, chunks = load_index(out_dir)
    return assemble_retriever(cfg, index, chunks)


def make_embedder(cfg: SweepConfig) -> Any:
    if cfg.embedding_kind == "ollama":
        return OllamaEmbedder(cfg.embedding_model)
    return SentenceTransformerEmbedder(cfg.embedding_model)


def make_query_embedder(cfg: SweepConfig) -> Any:
    if cfg.embedding_kind == "ollama":
        return OllamaEmbedder(cfg.embedding_model)
    inner = SentenceTransformerEmbedder(cfg.embedding_model)
    if "bge" in cfg.embedding_model.lower():
        return PrefixedQueryEmbedder(inner, BGE_QUERY_INSTRUCTION)
    return inner


def make_reranker(cfg: SweepConfig) -> Any:
    if not cfg.reranker_model:
        return None
    if cfg.reranker_model == QWEN_RERANKER:
        return PinnedQwenReranker(QWEN_RERANKER_REVISION)
    return CrossEncoderReranker(cfg.reranker_model)


def assemble_retriever(cfg: SweepConfig, index: Any, chunks: list[ChunkRecord]) -> Retriever:
    rag_config = load_config()
    return Retriever(
        rag_config,
        index,
        chunks,
        make_embedder(cfg),
        make_reranker(cfg),
        make_query_embedder(cfg),
    )


def full_config_sha(cfg: SweepConfig) -> str:
    payload = json.dumps(asdict(cfg), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_retriever(cfg: SweepConfig, articles: list[Any]) -> tuple[Retriever, str]:
    """Return the retriever and a note on where its index came from."""
    rag_config = load_config()
    if is_pinned_baseline(cfg):
        index_dir = rag_config.index_path(cfg.chunk_size)
        retriever = Retriever.from_index_dir(
            rag_config,
            index_dir,
            SentenceTransformerEmbedder(cfg.embedding_model),
            CrossEncoderReranker(cfg.reranker_model),
        )
        return retriever, f"committed production index at {index_dir}"
    return build_or_load_sweep_index(cfg, articles), "sweep index under data/index/sweeps/"


# --- splits ------------------------------------------------------------------


def load_tuning() -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = json.loads(
        (ROOT / "src" / "rag_agent" / "eval_questions.json").read_text("utf-8")
    )
    return raw


def dev_v1_ids() -> list[int]:
    return list(json.loads((ROOT / "data" / "dev_v1.sha256.json").read_text("utf-8"))["ids"])


def select_dev_ids(tuning: list[dict[str, Any]], split: str) -> tuple[list[int], str]:
    if split == "dev_v1":
        return dev_v1_ids(), "ids frozen in data/dev_v1.sha256.json"
    if split == "dev_65":
        return list(range(len(tuning))), "all tuning-65 questions"
    if split != "dev_40":
        raise SystemExit(f"unknown dev split: {split}")
    base = set(dev_v1_ids())
    rng = random.Random(GROW_SEED)  # noqa: S311 - seeded reproducibility, not security
    picked = list(base)
    for category in CATEGORY_ORDER:
        have = sum(1 for i in picked if tuning[i]["category"] == category)
        need = DEV40_TARGETS[category] - have
        if need <= 0:
            continue
        pool = [i for i, q in enumerate(tuning) if q["category"] == category and i not in base]
        picked.extend(rng.sample(pool, need))
    return sorted(picked), "dev_v1 union seed-43 complement sampling to 24/8/8"


def load_items(split: str, articles: list[Any]) -> tuple[list[Item], str, str]:
    """Return items, the set sha256, and a provenance note for the split."""
    title_to_id = {a.title: a.article_id for a in articles}
    if split == "final_v3":
        path = ROOT / "data" / "golden_final_v3.json"
        raw = json.loads(path.read_text("utf-8"))
        items = [
            Item(
                question=r["question"],
                category=r["category"],
                behavior=r["expected_behavior"],
                gold_article_ids={
                    title_to_id[t] for t in r.get("relevant_titles", []) if t in title_to_id
                },
                gold_chunk_ids=set(r.get("gold_chunk_ids", [])),
                absent_terms=list(r.get("absent_terms", [])),
            )
            for r in raw
        ]
        return items, sha256_file(path), "golden_final_v3.json (exact gold_chunk_ids)"

    tuning = load_tuning()
    ids, note = select_dev_ids(tuning, split)
    items = []
    for i in ids:
        q = tuning[i]
        titles = q.get("relevant_titles") or []
        resolved = {title_to_id[t] for t in titles if t in title_to_id}
        missing = [t for t in titles if t not in title_to_id]
        if q.get("expected_behavior", "answer") == "answer" and not resolved:
            raise SystemExit(f"dev question {i} has no resolvable gold titles: {q['question']!r}")
        if missing:
            logger.warning("dev question %d: titles not in corpus ignored: %s", i, missing)
        items.append(
            Item(
                question=q["question"],
                category=q["category"],
                behavior=q.get("expected_behavior", "answer"),
                gold_article_ids=resolved,
            )
        )
    set_sha = hashlib.sha256(json.dumps(ids, sort_keys=True).encode("utf-8")).hexdigest()
    return items, set_sha, f"{note}; ids recorded in report"


# --- metrics -----------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def measure(retriever: Retriever, items: list[Item], cfg: SweepConfig) -> dict[str, Any]:
    answerable = [i for i in items if i.behavior == "answer"]
    slices: dict[str, dict[str, Any]] = {}
    ranks: list[int | None] = []
    tokens3: list[int] = []
    tokens5: list[int] = []
    false_evidence = 0
    run_chunk_ids = {c.chunk_id for c in retriever.chunks}

    def gold_for(item: Item) -> tuple[set[str], str]:
        """Chunk-level gold ids that exist in this run's chunk set.

        final_v3 gold ids are authored on the chunk-200 layout; a candidate
        with a different chunking falls back to article-level gold (every
        chunk of the gold articles) so recall stays meaningful — the mode is
        recorded in the report.
        """
        if item.gold_chunk_ids:
            exact = item.gold_chunk_ids & run_chunk_ids
            if len(exact) >= max(1, len(item.gold_chunk_ids) // 2):
                return exact, "chunk_exact"
        article_gold = {
            c.chunk_id for c in retriever.chunks if c.article_id in item.gold_article_ids
        }
        if item.gold_chunk_ids:
            return article_gold, "article_fallback"
        return article_gold, "article_level"

    gold_modes: set[str] = set()

    def token_total(chunk_ids: list[str]) -> int:
        total = 0
        for cid in chunk_ids:
            chunk = retriever.get_chunk(cid)
            if chunk is not None:
                total += chunk.token_count
        return total

    for item in answerable:
        citations = retriever.search(item.question, top_k=cfg.measure_k)
        ranked = [c.chunk_id for c in citations]
        gold, gold_mode = gold_for(item)
        gold_modes.add(gold_mode)
        rank = next((r + 1 for r, cid in enumerate(ranked) if cid in gold), None)
        ranks.append(rank)
        tokens5.append(token_total(ranked))
        tokens3.append(token_total(ranked[: cfg.top_k]))
        slice_ = slices.setdefault(item.category, {"n": 0, "hits5": 0, "ranks": []})
        slice_["n"] += 1
        slice_["ranks"].append(rank)
        if rank is not None and rank <= 5:
            slice_["hits5"] += 1

    for item in [i for i in items if i.behavior != "answer"]:
        if not item.absent_terms:
            continue
        citations = retriever.search(item.question, top_k=cfg.measure_k)
        text = " ".join(c.excerpt for c in citations).lower()
        if any(term.lower() in text for term in item.absent_terms):
            false_evidence += 1

    n = len(answerable)
    hits5 = sum(1 for r in ranks if r is not None and r <= 5)
    mrr = sum(1.0 / r for r in ranks if r is not None) / n if n else 0.0
    return {
        "n_answerable": n,
        "gold_modes": sorted(gold_modes),
        "recall_at_5": hits5 / n if n else 0.0,
        "recall_at_5_wilson95": list(wilson(hits5, n)),
        "mrr_at_5": mrr,
        "mean_context_tokens_top3": sum(tokens3) / n if n else 0.0,
        "mean_context_tokens_top5": sum(tokens5) / n if n else 0.0,
        "slices": {
            name: {
                "n": s["n"],
                "recall_at_5": s["hits5"] / s["n"] if s["n"] else 0.0,
                "mrr_at_5": (
                    sum(1.0 / r for r in s["ranks"] if r is not None) / s["n"] if s["n"] else 0.0
                ),
            }
            for name, s in sorted(slices.items())
        },
        "n_abstain_false_evidence": false_evidence,
    }


# --- outputs -----------------------------------------------------------------


def report_path_for(cfg: SweepConfig, split: str) -> Path:
    if cfg.name == "baseline":
        out = ROOT / "reports" / "retrieval_baseline" / f"{split}.json"
    else:
        out = ROOT / "reports" / "retrieval_sweeps" / f"{cfg.name}__{split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def append_log(row: dict[str, Any]) -> None:
    path = ROOT / "reports" / "experiment_log.json"
    rows = json.loads(path.read_text("utf-8")) if path.exists() else []
    rows.append(row)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    split, config_path = parse_args()
    cfg = load_sweep_config(config_path)
    rag_config = load_config()
    articles = load_corpus(rag_config)

    grabber = HostGrabber()
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.addHandler(grabber)
    httpx_logger.setLevel(logging.INFO)

    items, set_sha, set_note = load_items(split, articles)
    try:
        retriever, index_note = build_retriever(cfg, articles)
    except Exception as exc:  # broad: model-load failures vary; recorded per arm
        row = {
            "ts": datetime.now(UTC).isoformat(),
            "step": "sweep",
            "change": cfg.name,
            "split": split,
            "config_sha256": full_config_sha(cfg),
            "decision": "not_run",
            "reason": f"retriever build failed: {exc}",
            "request_hosts": sorted({h for h in grabber.hosts if h}),
        }
        append_log(row)
        out = report_path_for(cfg, split)
        out.write_text(
            json.dumps({"config": asdict(cfg), "not_run": row["reason"]}, indent=2) + "\n"
        )
        logger.error("arm %s not run: %s", cfg.name, exc)
        return 0

    metrics = measure(retriever, items, cfg)
    hosts = sorted({h for h in grabber.hosts if h})
    bad = [h for h in hosts if h not in LOCAL_HOSTS]
    if bad:
        raise SystemExit(f"STOP: non-local request hosts observed: {bad}")

    report = {
        "schema_version": "measure-retrieval-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "step": "baseline" if cfg.name == "baseline" else "sweep",
        "split": split,
        "config": asdict(cfg),
        "config_sha256": full_config_sha(cfg),
        "set_sha256": set_sha,
        "set_note": set_note,
        "commit": git_commit(),
        "dirty": git_dirty(),
        "index_note": index_note,
        "method": (
            "retrieval-only; no LLM calls. Measurement ranks top_k=5 "
            f"({cfg.candidates()} candidates fetched = measure_k x rerank_multiplier, "
            "README '5xk'); production serving slice is top_k=3 — both token means "
            "reported. Dev gold is article-level (all chunks of relevant_titles "
            "articles); final_v3 gold is exact gold_chunk_ids."
        ),
        "rerank_review": (
            {
                "model": QWEN_RERANKER,
                "revision": QWEN_RERANKER_REVISION,
                "trust_remote_code": False,
                "review": "cached snapshot contains no remote-code files "
                "(no modeling_*.py/configuration_*.py); native transformers load",
            }
            if cfg.reranker_model == QWEN_RERANKER
            else None
        ),
        "request_hosts": hosts,
        "metrics": metrics,
    }
    out = report_path_for(cfg, split)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    append_log(
        {
            "ts": report["generated_at"],
            "step": report["step"],
            "change": cfg.name,
            "split": split,
            "config_sha256": report["config_sha256"],
            "set_sha256": set_sha,
            "n_answerable": metrics["n_answerable"],
            "recall_at_5": metrics["recall_at_5"],
            "recall_at_5_wilson95": metrics["recall_at_5_wilson95"],
            "mrr_at_5": metrics["mrr_at_5"],
            "mean_context_tokens_top3": metrics["mean_context_tokens_top3"],
            "mean_context_tokens_top5": metrics["mean_context_tokens_top5"],
            "report_path": str(out.relative_to(ROOT)),
            "request_hosts": hosts,
            "decision": "baseline" if cfg.name == "baseline" else "measured",
        }
    )
    logger.info(
        "%s/%s recall@5 %.4f MRR@5 %.4f (n=%d) hosts=%s",
        cfg.name,
        split,
        metrics["recall_at_5"],
        metrics["mrr_at_5"],
        metrics["n_answerable"],
        hosts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
