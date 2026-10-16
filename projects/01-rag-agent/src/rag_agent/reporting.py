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


# Deterministic abstention rule: the model refused to answer. Documented and
# unit-tested; low-confidence OR explicit no-evidence phrasing in the summary.
ABSTENTION_MARKERS = (
    "no relevant",
    "no evidence",
    "no information",
    "cannot answer",
    "can't answer",
    "not found",
    "unable to",
    "no passage",
)


@dataclass
class QuestionTrace:
    """Per-question evaluation record: the failure-taxonomy input."""

    question: str
    category: str  # single_hop | multi_hop | unanswerable
    expected_behavior: str  # answer | abstain
    top_rank: int | None  # 1-based rank of first relevant chunk in top-10 (None = not found)
    retrieved_relevant: bool  # relevant chunk within the production top_k
    cited_relevant: bool  # the agent cited at least one relevant article
    faithfulness: float  # per-row judge score (NaN when the run failed)
    abstained: bool
    format_ok: bool  # False when the agent run raised / output was invalid
    error: str = ""


def is_abstention(summary: str, confidence: float) -> bool:
    """Deterministic refusal detector (rule documented in module docstring)."""
    lowered = summary.lower()
    return confidence < 0.3 or any(marker in lowered for marker in ABSTENTION_MARKERS)


def classify_question(trace: QuestionTrace) -> str:
    """Failure taxonomy, first match wins (rules documented):

    1. ``format-failure`` — the agent run raised or returned schema-invalid output.
    2. abstain-expected + abstained → ``correct`` (refusing is the right answer).
    3. abstain-expected + answered → ``unsupported-claim`` (claims without evidence).
    4. ``retrieval-miss`` — answerable but no relevant chunk in the production top_k.
    5. ``unsupported-claim`` — relevant evidence found but the judge scores the
       answer below 0.5 (claims not supported by the context).
    6. ``correct`` — everything else.
    """
    if not trace.format_ok:
        return "format-failure"
    if trace.expected_behavior == "abstain":
        return "correct" if trace.abstained else "unsupported-claim"
    if not trace.retrieved_relevant:
        return "retrieval-miss"
    if trace.faithfulness < 0.5:
        return "unsupported-claim"
    return "correct"


def abstention_report(
    traces: list[QuestionTrace], n_resamples: int = 1000, seed: int = 42
) -> dict[str, Any]:
    """Refusal accuracy, cite-when-expected, and false-abstention rates + CIs.

    Each rate is a mean over per-question 0/1 indicators; the 95% CI is the
    percentile bootstrap (``n_resamples`` draws, seeded) over those indicators.
    """
    unanswerable = [t for t in traces if t.expected_behavior == "abstain"]
    answerable = [t for t in traces if t.expected_behavior == "answer"]
    refused_flags = [1.0 if t.abstained else 0.0 for t in unanswerable]
    cited_flags = [1.0 if t.cited_relevant else 0.0 for t in answerable]
    false_abstain_flags = [1.0 if t.abstained else 0.0 for t in answerable]
    return {
        "n_unanswerable": len(unanswerable),
        "n_answerable": len(answerable),
        "refusal_accuracy": (
            sum(refused_flags) / len(unanswerable) if unanswerable else float("nan")
        ),
        "refusal_accuracy_ci95": (
            list(bootstrap_ci(refused_flags, n_resamples=n_resamples, seed=seed))
            if unanswerable
            else [float("nan"), float("nan")]
        ),
        "cite_when_expected": (sum(cited_flags) / len(answerable) if answerable else float("nan")),
        "cite_when_expected_ci95": (
            list(bootstrap_ci(cited_flags, n_resamples=n_resamples, seed=seed))
            if answerable
            else [float("nan"), float("nan")]
        ),
        "false_abstention_rate": (
            sum(false_abstain_flags) / len(answerable) if answerable else float("nan")
        ),
        "false_abstention_rate_ci95": (
            list(bootstrap_ci(false_abstain_flags, n_resamples=n_resamples, seed=seed))
            if answerable
            else [float("nan"), float("nan")]
        ),
    }


def bootstrap_ci(
    values: list[float], n_resamples: int = 1000, seed: int = 42
) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for a mean (NaN values dropped)."""
    import random as _random

    clean = [v for v in values if v == v]
    if not clean:
        return (float("nan"), float("nan"))
    rng = _random.Random(seed)
    means = []
    for _ in range(n_resamples):
        sample = [clean[rng.randrange(len(clean))] for _ in range(len(clean))]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo = means[max(0, int(0.025 * n_resamples))]
    hi = means[min(n_resamples - 1, int(0.975 * n_resamples))]
    return (round(lo, 4), round(hi, 4))


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
    traces: list[QuestionTrace] = field(default_factory=list)
    input_tokens: list[int] = field(default_factory=list)
    output_tokens: list[int] = field(default_factory=list)
    faithfulness_rows: list[float] = field(default_factory=list)
    relevance_rows: list[float] = field(default_factory=list)
    retrieved_rows: list[float] = field(default_factory=list)

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
    traces: list[QuestionTrace] | None = None,
    meta: dict[str, Any] | None = None,
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
    if meta:
        metrics["_meta"] = meta
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    if traces:
        write_question_traces(config, traces)
        inject_trace_section(config, traces)
    logger.info("report written: %s", config.reports_dir / "report.html")


def write_question_traces(config: RAGConfig, traces: list[QuestionTrace]) -> Path:
    """Persist the per-question trace table the report links to."""
    rows = [
        {
            "question": t.question,
            "category": t.category,
            "expected_behavior": t.expected_behavior,
            "top_rank": t.top_rank,
            "retrieved_relevant": t.retrieved_relevant,
            "cited_relevant": t.cited_relevant,
            "faithfulness": t.faithfulness,
            "abstained": t.abstained,
            "format_ok": t.format_ok,
            "verdict": classify_question(t),
            "error": t.error,
        }
        for t in traces
    ]
    path = config.reports_dir / "question_traces.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return path


def inject_trace_section(config: RAGConfig, traces: list[QuestionTrace]) -> None:
    """Append a compact per-question trace table to report.html (links the JSON)."""
    report_path = config.reports_dir / "report.html"
    if not report_path.exists():
        return
    max_rows = 40
    header = (
        "<h2>Per-question trace</h2>"
        '<p>Full table: <a href="question_traces.json"><code>question_traces.json</code></a></p>'
        "<table><tr><th>question</th><th>category</th><th>expected</th><th>top rank</th>"
        "<th>cited</th><th>verdict</th></tr>"
    )
    rows_html = []
    for t in traces[:max_rows]:
        rows_html.append(
            "<tr>"
            f"<td>{_html_escape(t.question[:90])}</td>"
            f"<td>{t.category}</td>"
            f"<td>{t.expected_behavior}</td>"
            f"<td>{t.top_rank if t.top_rank is not None else '—'}</td>"
            f"<td>{'✓' if t.cited_relevant else '—'}</td>"
            f"<td>{classify_question(t)}</td>"
            "</tr>"
        )
    section = header + "".join(rows_html) + "</table>"
    html = report_path.read_text(encoding="utf-8")
    if "</body>" in html:
        html = html.replace("</body>", f"{section}</body>")
        report_path.write_text(html, encoding="utf-8")


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
