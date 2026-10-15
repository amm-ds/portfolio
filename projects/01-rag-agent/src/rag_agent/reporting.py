"""Shared measurement types, telemetry and report assembly.

Holds the dataclasses the orchestrator (:mod:`rag_agent.evaluate`) produces and
the figure builders (:mod:`rag_agent.figures`) consume, plus the metrics.json /
cost-telemetry writing. Kept free of orchestration and plotting imports so both
sides can depend on it without cycles.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.rag import RAGEvalResult

from rag_agent.config import RAGConfig
from rag_agent.ragas_eval import RagasRow
from rag_agent.schemas import EvalQuestion

if TYPE_CHECKING:
    import plotly.graph_objects as go

logger = get_logger(__name__)

# Rough tokens-per-word assumption for estimating prompt context sizes when the
# provider does not report per-section usage.
TOKENS_PER_WORD = 1.3
BASE_PROMPT_TOKENS = 220  # system prompt + tool schemas + message envelope
TOP_K_VALUES: tuple[int, ...] = (3, 5, 8, 10)


class TopkData(TypedDict):
    """Per-chunk-size grid from one top-max(k) search pass."""

    ranks: list[int | None]
    token_sums: list[list[int]]  # cumulative citation tokens at each rank
    n_chunks: int


@dataclass
class RetrievalScores:
    """Retrieval quality for one chunk-size index."""

    chunk_size: int
    recall_at_5: float
    recall_at_10: float
    mrr_at_5: float
    n_questions: int

    def as_run(self, name: str | None = None) -> RunResult:
        return RunResult(
            name=name or f"retrieval_chunks_{self.chunk_size}",
            metrics=[
                MetricResult(name="recall@5", value=self.recall_at_5),
                MetricResult(name="recall@10", value=self.recall_at_10),
                MetricResult(name="mrr@5", value=self.mrr_at_5),
            ],
        )


@dataclass
class RAGRun:
    """RAG quality + ops measurements for one agent configuration."""

    eval_result: RAGEvalResult
    latencies_s: list[float] = field(default_factory=list)
    ragas_rows: list[RagasRow] = field(default_factory=list)
    input_tokens: list[int] = field(default_factory=list)
    output_tokens: list[int] = field(default_factory=list)

    @property
    def p50_latency_s(self) -> float:
        return _percentile(self.latencies_s, 0.50)

    @property
    def p95_latency_s(self) -> float:
        return _percentile(self.latencies_s, 0.95)

    def cost_per_query_usd(self, avg_input_tokens: float) -> float:
        """Cost estimate at ``avg_input_tokens`` input + measured avg output tokens."""
        avg_out = sum(self.output_tokens) / len(self.output_tokens) if self.output_tokens else 0.0
        return avg_input_tokens / 1e6 * self._rate_in + avg_out / 1e6 * self._rate_out

    @property
    def est_cost_per_query_usd(self) -> float:
        """Cost from agent-recorded usage."""
        if not self.input_tokens:
            return float("nan")
        avg_in = sum(self.input_tokens) / len(self.input_tokens)
        return self.cost_per_query_usd(avg_in)

    _rate_in: float = 0.15
    _rate_out: float = 0.60

    def as_run(self, name: str, input_tokens_override: float | None = None) -> RunResult:
        d = self.eval_result.to_dict()
        avg_in = (
            input_tokens_override
            if input_tokens_override is not None
            else (sum(self.input_tokens) / len(self.input_tokens) if self.input_tokens else 0.0)
        )
        metrics = [
            MetricResult(name="faithfulness", value=float(d["faithfulness"])),
            MetricResult(name="answer_relevance", value=float(d["answer_relevance"])),
            MetricResult(name="context_recall", value=float(d["context_recall"])),
            MetricResult(name="p50_latency_s", value=self.p50_latency_s, higher_is_better=False),
            MetricResult(name="p95_latency_s", value=self.p95_latency_s, higher_is_better=False),
            MetricResult(
                name="est_cost_usd_per_query",
                value=self.cost_per_query_usd(avg_in),
                higher_is_better=False,
            ),
        ]
        return RunResult(name=name, metrics=metrics)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


def recall_at_k(ranks: list[int | None], k: int) -> float:
    """Fraction of questions with a relevant article within the top ``k`` hits."""
    if not ranks:
        return float("nan")
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)


def recall_at_k_from(topk_data: TopkData, k: int) -> float:
    return recall_at_k(topk_data["ranks"], k)


def mrr_at_5(ranks: list[int | None]) -> float:
    if not ranks:
        return float("nan")
    return sum(1.0 / r for r in ranks if r is not None and r <= 5) / len(ranks)


def est_input_tokens_at(topk_data: TopkData, questions: list[EvalQuestion], k: int) -> float:
    """Average estimated input tokens/query at top-``k`` for one chunk size."""
    token_sums = topk_data["token_sums"]
    total = 0.0
    for q, sums in zip(questions, token_sums, strict=True):
        q_words = len(q.question.split())
        context_words = sums[k - 1] if k <= len(sums) else (sums[-1] if sums else 0)
        total += BASE_PROMPT_TOKENS + q_words * TOKENS_PER_WORD + context_words * TOKENS_PER_WORD
    return total / max(len(questions), 1)


def topk_run_for_size(size: int, topk_data: TopkData) -> RunResult:
    """One run row per chunk size carrying the full recall@k grid."""
    metrics = [
        MetricResult(name=f"recall@{k}", value=recall_at_k_from(topk_data, k)) for k in TOP_K_VALUES
    ]
    metrics.append(MetricResult(name="mrr@5", value=mrr_at_5(topk_data["ranks"])))
    return RunResult(name=f"retrieval_topk_sweep_chunks_{size}", metrics=metrics)


def inference_backend() -> str:
    """Human-readable backend label: env provider or local Ollama model."""
    from portfolio_core.config import get_settings
    from portfolio_core.llm import DEFAULT_OLLAMA_MODEL

    s = get_settings()
    if s.llm_api_key and s.llm_base_url:
        return f"env:{s.llm_model or 'kimi-k2-0711-preview'}"
    return f"ollama:{os.environ.get('OLLAMA_MODEL', DEFAULT_OLLAMA_MODEL)}"


def cost_telemetry(config: RAGConfig, rag_run: RAGRun, wall_time_s: float) -> dict[str, Any]:
    """Per-query token usage + cost framing for the telemetry artifact.

    Local inference (Ollama) has $0 API cost; the rate-card numbers are kept as
    a clearly-labelled hypothetical for budget comparisons with hosted models.
    """
    hypothetical = [
        round(
            in_tok / 1e6 * config.usd_per_mtok_input + out_tok / 1e6 * config.usd_per_mtok_output,
            8,
        )
        for in_tok, out_tok in zip(rag_run.input_tokens, rag_run.output_tokens, strict=False)
    ]
    backend = inference_backend()
    return {
        "backend": backend,
        "api_cost_usd": 0.0 if backend.startswith("ollama:") else None,
        "note": (
            "local inference: $0 API cost; eval is CPU/GPU-bound "
            f"(~{wall_time_s / 60:.1f} min wall time)"
        ),
        "n_queries": len(hypothetical),
        "total_input_tokens": sum(rag_run.input_tokens),
        "total_output_tokens": sum(rag_run.output_tokens),
        "eval_wall_time_s": round(wall_time_s, 1),
        "rate_card": {
            "usd_per_mtok_input": config.usd_per_mtok_input,
            "usd_per_mtok_output": config.usd_per_mtok_output,
        },
        "rate_card_hypothetical_cost_usd": {
            "total": round(sum(hypothetical), 8),
            "mean": round(sum(hypothetical) / max(len(hypothetical), 1), 8),
            "p50": round(_percentile(hypothetical, 0.50), 8),
            "p95": round(_percentile(hypothetical, 0.95), 8),
        },
        "per_query": [
            {"input_tokens": in_tok, "output_tokens": out_tok}
            for in_tok, out_tok in zip(rag_run.input_tokens, rag_run.output_tokens, strict=False)
        ],
    }


def write_cost_telemetry(config: RAGConfig, rag_run: RAGRun, wall_time_s: float) -> Path:
    """Write ``reports/cost_telemetry.json`` for the active inference backend."""
    payload = cost_telemetry(config, rag_run, wall_time_s)
    path = config.reports_dir / "cost_telemetry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("cost telemetry written: %s (backend=%s)", path, payload["backend"])
    return path


def write_reports(
    config: RAGConfig,
    scores: list[RetrievalScores],
    rag_run: RAGRun | None,
    figures: dict[str, "go.Figure"],
    extra_metrics: dict[str, Any],
    rag_input_tokens_override: float | None = None,
    random_scores: list[RetrievalScores] | None = None,
    model_scores: dict[str, RetrievalScores] | None = None,
    rerank_scores: dict[str, RetrievalScores] | None = None,
    topk_runs: list[RunResult] | None = None,
    ragas_scores: dict[str, float] | None = None,
) -> None:
    """Assemble report.html + figures + metrics.json (RunBuilder + detail block)."""
    from portfolio_eval.report import ReportBuilder

    builder = ReportBuilder(
        title="01-rag-agent — evaluation report", figures_dir=config.reports_dir / "figures"
    )
    for s in scores:
        builder.add_run(s.as_run())
    for s in random_scores or []:
        builder.add_run(s.as_run(f"retrieval_random_chunks_{s.chunk_size}"))
    for slug, s in (model_scores or {}).items():
        builder.add_run(s.as_run(f"retrieval_model_{slug}_chunks_{s.chunk_size}"))
    for label, s in (rerank_scores or {}).items():
        builder.add_run(s.as_run(f"retrieval_rerank_{label}_chunks_{s.chunk_size}"))
    for run in topk_runs or []:
        builder.add_run(run)
    if rag_run is not None:
        builder.add_run(
            rag_run.as_run("rag_agent", input_tokens_override=rag_input_tokens_override)
        )
    if ragas_scores:
        builder.add_run(
            RunResult(
                name="ragas",
                metrics=[MetricResult(name=k, value=v) for k, v in ragas_scores.items()],
            )
        )
    builder.build(config.reports_dir, figures=figures)
    # Persist machine-readable figure payloads for the showcase app.
    for name, fig in figures.items():
        save_json(fig, config.reports_dir / "figures" / f"{name}.json")
    # Augment metrics.json with the full detail the README cites.
    metrics_path = config.reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["detail"] = extra_metrics
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    logger.info("report written: %s", config.reports_dir / "report.html")
