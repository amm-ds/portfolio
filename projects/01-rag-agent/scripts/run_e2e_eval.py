"""End-to-end RAG evaluation runner — Phase E (20261123 handoff).

``--split dev_v1``: the 20 questions frozen in ``data/dev_v1.sha256.json``
(indices into ``src/rag_agent/eval_questions.json``) run through
``run_rag_eval`` against the production S3 retriever
(``data/index/chunks_200`` + MiniLM + ms-marco rerank + RRF fusion +
per-article cap from ``params.yaml``), checkpointed under
``reports/runs/dev_v1-<sha12>/``. Writes ``reports/e2e_dev_v1/``:
``metrics.json``, ``question_traces.json``, ``f1_summary.json``.

``--summarize <reports_dir>``: recompute the roadmap F1 summary from
``question_traces*.json`` inside ``<reports_dir>`` and write
``<reports_dir>/f1_summary.json``.

F1 definitions (handoff): TP = answerable, answered (not abstained),
verdict "correct", cited_relevant; FN = any other answerable row. TN =
unanswerable, abstained, verdict "correct"; FP = any other unanswerable row.

    uv run python scripts/run_e2e_eval.py --split dev_v1
    uv run python scripts/run_e2e_eval.py --summarize reports/final_v3_e2e
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger
from rag_agent.agent import build_agent
from rag_agent.cli import load_config
from rag_agent.corpus import load_corpus
from rag_agent.evaluate import load_questions, run_rag_eval
from rag_agent.index import CrossEncoderReranker, Retriever, SentenceTransformerEmbedder
from rag_agent.judge import RUBRIC_SYSTEM_PROMPT
from rag_agent.reporting import trace_to_row
from rag_agent.runner import (
    RUNS_ROOT,
    Checkpoint,
    HostGrabber,
    RunManifest,
    config_hash,
    git_commit,
    git_dirty,
    make_run_id,
    seed_spend_from_manifest,
)

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "reports" / "experiment_log.json"
PERMITTED_HOSTS = {"localhost", "127.0.0.1", None, "api.kimi.com"}


def append_log(row: dict[str, Any]) -> None:
    rows = json.loads(LOG.read_text("utf-8")) if LOG.exists() else []
    rows.append(row)
    LOG.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [max(0.0, center - half), min(1.0, center + half)]


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Roadmap F1 / precision / recall / accuracy + error breakdown."""
    tp = fp = tn = fn = 0
    errors: dict[str, int] = {
        "unsupported_claim": 0,
        "false_abstention": 0,
        "wrong_abstention": 0,
        "budget_terminated": 0,
        "format_failure": 0,
        "uncited_relevant": 0,
    }
    for row in rows:
        answerable = row["expected_behavior"] == "answer"
        abstained = bool(row["abstained"])
        verdict = row["verdict"]
        if verdict == "unsupported-claim":
            errors["unsupported_claim"] += 1
        if verdict == "empty-answer":
            errors["false_abstention"] += 1
        if verdict == "budget-terminated":
            errors["budget_terminated"] += 1
        if verdict == "format-failure":
            errors["format_failure"] += 1
        if answerable:
            if row["retrieved_relevant"] and not row["cited_relevant"]:
                errors["uncited_relevant"] += 1
            if (not abstained) and verdict == "correct" and row["cited_relevant"]:
                tp += 1
            else:
                fn += 1
        else:
            if not abstained and verdict not in ("budget-terminated", "format-failure"):
                errors["wrong_abstention"] += 1
            if abstained and verdict == "correct":
                tn += 1
            else:
                fp += 1
    n = len(rows)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    return {
        "n_questions": n,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "overall_accuracy": round(accuracy, 4),
        "overall_accuracy_wilson95": [round(x, 4) for x in wilson(tp + tn, n)],
        "errors": errors,
    }


def load_rows(reports_dir: Path) -> list[dict[str, Any]]:
    for name in ("question_traces.json", "question_traces_heldout.json"):
        path = reports_dir / name
        if path.exists():
            rows: list[dict[str, Any]] = json.loads(path.read_text("utf-8"))
            if rows:
                return rows
    raise SystemExit(f"no question_traces*.json with rows under {reports_dir}")


def summarize(reports_dir: Path) -> dict[str, Any]:
    rows = load_rows(reports_dir)
    summary = summarize_rows(rows)
    summary["generated_at"] = datetime.now(UTC).isoformat()
    summary["source_traces"] = str(reports_dir)
    out = reports_dir / "f1_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    append_log(
        {
            "ts": summary["generated_at"],
            "step": "e2e",
            "change": reports_dir.name,
            "split": reports_dir.name,
            "decision": "summarized",
            "f1": summary["f1"],
            "precision": summary["precision"],
            "recall": summary["recall"],
            "overall_accuracy": summary["overall_accuracy"],
            "errors": summary["errors"],
            "report_path": str(out),
        }
    )
    logger.info(
        "%s f1=%.4f precision=%.4f recall=%.4f accuracy=%.4f",
        reports_dir.name,
        summary["f1"],
        summary["precision"],
        summary["recall"],
        summary["overall_accuracy"],
    )
    return summary


def prune_checkpoint_for_retry(run_dir: Path, manifest: RunManifest) -> None:
    """--retry-failed: keep only correct rows so the checkpoint re-runs failures."""
    rows_path = run_dir / "rows.jsonl"
    if rows_path.exists():
        kept = [
            line
            for line in rows_path.read_text("utf-8").splitlines()
            if line.strip() and json.loads(line).get("trace", {}).get("verdict") == "correct"
        ]
        rows_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        logger.info("retry-failed: kept %d correct checkpoint rows", len(kept))
    manifest_path = run_dir / "manifest.json"
    prior = 0.0
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text("utf-8")).get("cumulative_spend_usd", 0.0)
    manifest.cumulative_spend_usd = prior
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2) + "\n", encoding="utf-8")


def run_dev_v1(retry_failed: bool = False) -> dict[str, Any]:
    config = load_config()
    articles = load_corpus(config)
    tuning = load_questions(config, articles)
    ids = json.loads((ROOT / "data" / "dev_v1.sha256.json").read_text("utf-8"))["ids"]
    questions = [tuning[i] for i in ids]
    if len(questions) != 20:
        raise SystemExit(f"expected 20 dev_v1 questions, got {len(questions)}")

    chosen = config.retrieval_best
    if chosen is None:
        raise SystemExit("config.retrieval_best is required")
    retriever = Retriever.from_index_dir(
        config,
        config.index_path(chosen.chunk_size),
        SentenceTransformerEmbedder(chosen.embedding_model),
        CrossEncoderReranker(config.reranker_model),
    )
    agent = build_agent(config)

    set_sha = hashlib.sha256(json.dumps(ids).encode("utf-8")).hexdigest()
    manifest = RunManifest(
        run_id=make_run_id("dev_v1", set_sha),
        config_hash=config_hash(config),
        commit=git_commit(),
        dirty=git_dirty(),
        split="dev_v1",
        set_sha256=set_sha,
        index_id=f"{chosen.embedding_slug}:{chosen.chunk_size}+rerank:{chosen.rerank}",
        judge_model=os.environ.get("LLM_MODEL", "kimi-for-coding"),
        judge_prompt_hash=hashlib.sha256(RUBRIC_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16],
    )
    if retry_failed:
        prune_checkpoint_for_retry(RUNS_ROOT / manifest.run_id, manifest)
    checkpoint = Checkpoint.open(RUNS_ROOT / manifest.run_id, manifest)
    seed_spend_from_manifest(checkpoint)

    grabber = HostGrabber()
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.addHandler(grabber)
    httpx_logger.setLevel(logging.INFO)

    run = run_rag_eval(
        config, agent, retriever, questions, checkpoint=checkpoint, skip_hashes=checkpoint.completed
    )
    # Merge fresh traces with checkpointed rows from any prior (e.g. resumed)
    # process: a fully-resumed run returns zero fresh traces but the rows are
    # complete in the checkpoint.
    from rag_agent.runner import question_hash

    rows_by_q: dict[str, dict[str, Any]] = {
        row["qhash"]: row["trace"] for row in checkpoint._rows.values()
    }
    for t in run.traces:
        rows_by_q[question_hash(t.question)] = trace_to_row(t)
    rows = [rows_by_q[question_hash(q.question)] for q in questions]
    checkpoint_hosts = sorted(
        {h for row in checkpoint._rows.values() for h in row.get("hosts", [])}
    )
    # The guard covers THIS process's calls; the earlier huggingface.co status
    # ping (attempt 1, now prevented by HF_HUB_OFFLINE=1) stays visible in the
    # reported hosts but cannot re-trigger the stop on a checkpoint resume.
    bad = [h for h in {h for h in grabber.hosts if h} if h not in PERMITTED_HOSTS]
    if bad:
        raise SystemExit(f"STOP: non-permitted request host(s): {bad}")

    out_dir = ROOT / "reports" / "e2e_dev_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "question_traces.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "split": "dev_v1",
                "run_id": manifest.run_id,
                "set_sha256": set_sha,
                "commit": manifest.commit,
                "dirty": manifest.dirty,
                "n_questions": len(questions),
                "request_hosts": sorted({h for h in {*grabber.hosts, *checkpoint_hosts} if h}),
                "faithfulness_rows": len(run.faithfulness_rows),
                "p50_latency_s": run.p50_latency_s,
                "verify_reports": len(run.verify_reports),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = summarize(out_dir)
    append_log(
        {
            "ts": summary["generated_at"],
            "step": "e2e",
            "change": "dev_v1_gate",
            "split": "dev_v1",
            "decision": "gate",
            "f1": summary["f1"],
            "budget_terminated": summary["errors"]["budget_terminated"],
            "request_hosts": sorted({h for h in {*grabber.hosts, *checkpoint_hosts} if h}),
            "run_id": manifest.run_id,
        }
    )
    return summary


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # embedding loads stay off the network
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev_v1"], default=None)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="re-run only non-correct checkpoint rows (keeps correct rows at $0)",
    )
    parser.add_argument("--summarize", type=Path, default=None, help="reports dir to summarize")
    args = parser.parse_args()
    if args.summarize:
        summary = summarize(args.summarize)
    elif args.split == "dev_v1":
        summary = run_dev_v1(retry_failed=args.retry_failed)
    else:
        parser.error("--split dev_v1 or --summarize <dir> is required")
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
