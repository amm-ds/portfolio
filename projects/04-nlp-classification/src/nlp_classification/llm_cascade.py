"""Leakage-safe selective LLM review for the strongest transformer artifact.

The threshold is fitted only on validation predictions. Test and fresh-holdout
labels are used solely for final metrics, never for routing or prompt content.

Every run persists one row per example (id, split, baseline prediction,
confidence, routed flag, LLM verdict, final prediction, gold) to
``reports/llm_cascade_rows_<date>.jsonl`` and a paired fresh-holdout report
(bootstrap intervals + exact McNemar) to ``reports/llm_cascade_paired_ci.json``.
The summary artifact ``reports/llm_cascade.json`` is the committed reference
run and is never overwritten: a re-run publishes beside it as a replication
(owner decision, grade pass 4 / E6).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import numpy as np
import plotly.graph_objects as go
import torch
from portfolio_core.config import get_settings
from portfolio_core.llm import build_model, hosted_model_settings, is_hosted_provider
from portfolio_core.llm_budget import meter_result
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sklearn import metrics as skm

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, load_ag_news, tokenize_dataset
from nlp_classification.evaluate import (
    load_tokenizer,
    mcnemar_exact,
    paired_accuracy_delta,
    paired_macro_f1_delta,
)
from nlp_classification.fresh_holdout import draw_fresh_holdout
from nlp_classification.model import (
    FULLDATA_MODEL_PATH,
    build_nn_model,
    load_nn_state_dict,
    predict_proba_nn,
)
from nlp_classification.shims import Dataset


class ReviewDecision(BaseModel):
    """One replacement class decision from the reviewing model."""

    label_index: int = Field(ge=0)
    rationale: str = Field(min_length=1, max_length=500)


class ReviewBatch(BaseModel):
    """Ordered decisions for one bounded batch of headlines."""

    decisions: list[ReviewDecision] = Field(min_length=1, max_length=8)


class Reviewer(Protocol):
    """Review only rows selected by the cascade; labels are never arguments."""

    input_tokens: int
    output_tokens: int
    latency_s: float
    cost_usd: float

    def review(self, texts: list[str], indices: list[int]) -> dict[int, ReviewDecision]: ...


class KimiReviewer:
    """Structured eight-row review through the platform's configured provider."""

    def __init__(self, label_names: list[str]) -> None:
        self.label_names = label_names
        self.input_tokens = 0
        self.output_tokens = 0
        self.latency_s = 0.0
        self.cost_usd = 0.0
        # Lazy on purpose: building the agent requires a configured provider,
        # and tests inject a fake via `reviewer._agent = ...` before first
        # use. Eager construction made the whole 04 suite depend on a local
        # Ollama/hosted key — the environment-dependent failure behind the
        # November nightly streak (CI has no provider at all).
        self._agent: Agent[None, ReviewBatch] | None = None

    def _ensure_agent(self) -> Agent[None, ReviewBatch]:
        if self._agent is None:
            self._agent = Agent(
                build_model(),
                output_type=ReviewBatch,
                system_prompt=(
                    "Classify every AG News headline into exactly one provided class. "
                    "Use only each headline and the class list; never invent another label. "
                    "Return one zero-based label_index and short rationale per input item, "
                    "in exactly the same order and count as the supplied items."
                ),
                model_settings=hosted_model_settings() if is_hosted_provider() else None,
            )
        return self._agent

    def review(self, texts: list[str], indices: list[int]) -> dict[int, ReviewDecision]:
        decisions: dict[int, ReviewDecision] = {}
        agent = self._ensure_agent()
        for start in range(0, len(indices), 8):
            batch = indices[start : start + 8]
            items = [{"index": index, "headline": texts[index]} for index in batch]
            prompt = (
                f"Classes (index:name): {list(enumerate(self.label_names))}\n"
                f"Items: {json.dumps(items, ensure_ascii=False)}"
            )
            started = time.perf_counter()
            result = agent.run_sync(prompt)
            self.latency_s += time.perf_counter() - started
            self.input_tokens += int(result.usage.input_tokens)
            self.output_tokens += int(result.usage.output_tokens)
            # Meter every call into the platform spend ledger: per-call log
            # lines plus the hard USD cap (LLM_COST_LIMIT_USD) that stops a
            # runaway review pass before it crosses budget.
            record = meter_result(result, get_settings().llm_model or "kimi-for-coding")
            self.cost_usd += float(record.spend_usd)
            if len(result.output.decisions) != len(batch):
                raise ValueError("review returned the wrong number of decisions")
            for index, decision in zip(batch, result.output.decisions, strict=True):
                if decision.label_index >= len(self.label_names):
                    raise ValueError(f"review returned invalid label {decision.label_index}")
                decisions[index] = decision
        return decisions


def _f1(y_true: list[int], y_pred: np.ndarray) -> float:
    return float(skm.f1_score(y_true, y_pred, average="macro", zero_division=0))


def fit_threshold(
    probas: np.ndarray,
    y_true: list[int],
    texts: list[str],
    candidates: list[float],
    reviewer: Reviewer,
) -> float:
    """Select validation macro-F1, breaking ties toward fewer hosted reviews."""
    confidence = probas.max(axis=1)
    review_indices = sorted({i for i, conf in enumerate(confidence) if conf < max(candidates)})
    decisions = reviewer.review(texts, review_indices)
    base = probas.argmax(axis=1)
    best_tau = min(candidates)
    best_key = (-1.0, len(candidates))
    for tau in sorted(candidates):
        routed = base.copy()
        for index, decision in decisions.items():
            if confidence[index] < tau:
                routed[index] = decision.label_index
        score = _f1(y_true, routed)
        n_reviews = sum(confidence[index] < tau for index in decisions)
        key = (score, -n_reviews)
        if key > best_key:
            best_tau = tau
            best_key = key
    return float(best_tau)


def route_rows(
    probas: np.ndarray, texts: list[str], threshold: float, reviewer: Reviewer
) -> tuple[np.ndarray, dict[int, ReviewDecision]]:
    """Route sub-threshold rows to the reviewer; return final labels + verdicts."""
    confidence = probas.max(axis=1)
    indices = [i for i, conf in enumerate(confidence) if conf < threshold]
    routed = probas.argmax(axis=1)
    decisions = reviewer.review(texts, indices)
    for index, decision in decisions.items():
        routed[index] = decision.label_index
    return routed, decisions


def apply_threshold(
    probas: np.ndarray, texts: list[str], threshold: float, reviewer: Reviewer
) -> np.ndarray:
    """Route only sub-threshold rows to the reviewer and return final labels."""
    routed, _ = route_rows(probas, texts, threshold, reviewer)
    return routed


def _rows_for_split(
    split: str,
    y_true: list[int],
    confidence: np.ndarray,
    baseline: np.ndarray,
    routed: np.ndarray,
    decisions: dict[int, ReviewDecision],
) -> list[dict[str, Any]]:
    """One persisted decision row per example (the paired-analysis input)."""
    return [
        {
            "id": f"{split}:{index}",
            "split": split,
            "baseline_pred": int(baseline[index]),
            "confidence": round(float(confidence[index]), 6),
            "routed": index in decisions,
            "llm_verdict": int(decisions[index].label_index) if index in decisions else None,
            "final_pred": int(routed[index]),
            "gold": int(y_true[index]),
        }
        for index in range(len(y_true))
    ]


def paired_fresh_report(
    rows: list[dict[str, Any]], *, n_bootstrap: int = 2000, seed: int = 42
) -> dict[str, Any]:
    """Paired cascade-vs-baseline intervals + exact McNemar on the fresh holdout."""
    fresh = [row for row in rows if row["split"] == "fresh holdout"]
    y_true = [int(row["gold"]) for row in fresh]
    baseline = [int(row["baseline_pred"]) for row in fresh]
    final = [int(row["final_pred"]) for row in fresh]
    return {
        "n_rows": len(fresh),
        "n_reviews": sum(1 for row in fresh if row["routed"]),
        "f1_macro": paired_macro_f1_delta(
            y_true, final, baseline, n_bootstrap=n_bootstrap, seed=seed
        ),
        "accuracy": paired_accuracy_delta(
            y_true, final, baseline, n_bootstrap=n_bootstrap, seed=seed
        ),
        "mcnemar": mcnemar_exact(y_true, final, baseline),
    }


def _predict_full(cfg: NLPConfig, dataset: Dataset, n_labels: int) -> np.ndarray:
    device = torch.device("cpu")
    tokenizer = load_tokenizer(cfg.model_name)
    tokenized = tokenize_dataset(dataset, tokenizer, cfg.max_length)
    model = build_nn_model(cfg, n_labels)
    model = load_nn_state_dict(model, cfg.models_dir / FULLDATA_MODEL_PATH, device)
    return predict_proba_nn(model, tokenized, device, cfg.batch_size)


def _label_names(cfg: NLPConfig) -> list[str]:
    return cast(list[str], json.loads((cfg.data_dir / "label_names.json").read_text()))


def _comparison_figure(
    result: dict[str, Any], paired_ci: dict[str, Any] | None = None
) -> go.Figure:
    labels = ["validation", "bounded test", "fresh holdout"]
    baseline = [result[split]["baseline_f1_macro"] for split in labels]
    cascade = [result[split]["cascade_f1_macro"] for split in labels]
    fig = go.Figure()
    fig.add_bar(x=labels, y=baseline, name="transformer")
    fig.add_bar(x=labels, y=cascade, name="transformer + selective Kimi review")
    fresh = result["fresh holdout"]
    if paired_ci is not None:
        # Error bar on the fresh pair: the interval of the gain (cascade minus
        # baseline) mapped onto the cascade bar, i.e. spanning
        # [baseline + lo, baseline + hi]. A separate trace keeps the two
        # committed bar traces byte-equal.
        lo, hi = (float(v) for v in paired_ci["f1_macro"]["ci_95"])
        center = float(fresh["cascade_f1_macro"])
        base = float(fresh["baseline_f1_macro"])
        fig.add_trace(
            go.Scatter(
                x=["fresh holdout"],
                y=[center],
                mode="markers",
                marker={"size": 1, "color": "rgba(0,0,0,0)"},
                error_y={
                    "type": "data",
                    "symmetric": False,
                    "array": [max(0.0, base + hi - center)],
                    "arrayminus": [max(0.0, center - (base + lo))],
                    "color": "#f2f5fa",
                    "thickness": 1.5,
                    "width": 8,
                },
                name="paired 95% CI of the fresh gain (replication)",
                hoverinfo="skip",
            )
        )
    fig.update_layout(
        title=(
            f"Reviewing {fresh['n_reviews']} uncertain items moves fresh macro-F1 "
            f"{fresh['baseline_f1_macro']:.4f} → {fresh['cascade_f1_macro']:.4f}: "
            "no measurable change"
        ),
        barmode="group",
        yaxis_title="macro-F1",
        yaxis_range=[0, 1],
    )
    add_takeaway(fig, "threshold fitted on validation only; test and fresh holdout are scored once")
    return apply_theme(fig)


def run_cascade(
    cfg: NLPConfig, *, reviewer: Reviewer | None = None, loader: Any = load_ag_news
) -> dict[str, Any]:
    """Fit validation routing, score test/fresh once, persist rows + paired CI.

    The committed ``reports/llm_cascade.json`` is the reference run and is
    never overwritten here; the re-run's summary lives inside
    ``reports/llm_cascade_paired_ci.json`` as a replication published beside
    it. The comparison figure keeps the committed bars and adds the paired
    interval of the fresh gain as an error bar.
    """
    labels = _label_names(cfg)
    val_ds = Dataset.load_from_disk(str(cfg.val_dir))
    test_ds = Dataset.load_from_disk(str(cfg.test_dir))
    val_proba = _predict_full(cfg, val_ds, len(labels))
    test_proba = _predict_full(cfg, test_ds, len(labels))
    resolved_reviewer = reviewer or KimiReviewer(labels)
    threshold = fit_threshold(
        val_proba,
        [int(v) for v in val_ds[LABEL_COLUMN]],
        list(val_ds[TEXT_COLUMN]),
        cfg.cascade_taus,
        resolved_reviewer,
    )

    fresh, provenance = draw_fresh_holdout(cfg, loader()["test"])
    fresh_proba = _predict_full(cfg, fresh, len(labels))
    result: dict[str, Any] = {
        "threshold": threshold,
        "challenger_model": get_settings().llm_model or "configured-hosted-model",
        "provenance": {
            "routing_fit": (
                "validation only; no test or fresh-holdout labels or examples used for tuning"
            ),
            "fresh_holdout": provenance,
        },
    }
    rows: list[dict[str, Any]] = []
    for split, ds, probas in (
        ("validation", val_ds, val_proba),
        ("bounded test", test_ds, test_proba),
        ("fresh holdout", fresh, fresh_proba),
    ):
        y_true = [int(v) for v in ds[LABEL_COLUMN]]
        confidence = probas.max(axis=1)
        baseline = probas.argmax(axis=1)
        routed, decisions = route_rows(probas, list(ds[TEXT_COLUMN]), threshold, resolved_reviewer)
        result[split] = {
            "baseline_f1_macro": _f1(y_true, baseline),
            "cascade_f1_macro": _f1(y_true, routed),
            "baseline_accuracy": float((baseline == np.asarray(y_true)).mean()),
            "cascade_accuracy": float((routed == np.asarray(y_true)).mean()),
            "n_reviews": int((confidence < threshold).sum()),
        }
        rows.extend(_rows_for_split(split, y_true, confidence, baseline, routed, decisions))

    improves = (
        result["bounded test"]["cascade_f1_macro"] > result["bounded test"]["baseline_f1_macro"]
    )
    fresh_holds = (
        result["fresh holdout"]["cascade_f1_macro"] >= result["fresh holdout"]["baseline_f1_macro"]
    )
    result["selected"] = "cascade" if improves and fresh_holds else "transformer"
    result["ops"] = {
        "input_tokens": resolved_reviewer.input_tokens,
        "output_tokens": resolved_reviewer.output_tokens,
        "review_latency_s": round(resolved_reviewer.latency_s, 3),
        "est_cost_usd": round(
            (resolved_reviewer.input_tokens + 4 * resolved_reviewer.output_tokens) / 1_000_000,
            6,
        ),
        "meter_spend_usd": round(resolved_reviewer.cost_usd, 6),
    }

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    rows_path = cfg.reports_dir / f"llm_cascade_rows_{stamp}.jsonl"
    with rows_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    paired = paired_fresh_report(rows)
    result["paired_fresh_holdout"] = paired

    committed_path = cfg.reports_dir / "llm_cascade.json"
    committed = (
        cast(dict[str, Any], json.loads(committed_path.read_text(encoding="utf-8")))
        if committed_path.exists()
        else None
    )
    replication_f1 = float(result["fresh holdout"]["cascade_f1_macro"])
    committed_f1 = (
        float(committed["fresh holdout"]["cascade_f1_macro"]) if committed is not None else None
    )
    divergence = abs(replication_f1 - committed_f1) if committed_f1 is not None else None
    ci_doc: dict[str, Any] = {
        "generated_by": "nlp_classification.cli llm-cascade",
        "generated_at": stamp,
        "rows_file": f"reports/{rows_path.name}",
        "committed_reference": "reports/llm_cascade.json",
        "protocol": (
            "threshold fitted on validation only; test and fresh holdout each scored "
            "once; one persisted decision row per example"
        ),
        "replication": {
            "threshold": result["threshold"],
            "challenger_model": result["challenger_model"],
            "selected": result["selected"],
            "validation": result["validation"],
            "bounded test": result["bounded test"],
            "fresh holdout": result["fresh holdout"],
            "ops": result["ops"],
        },
        "fresh_holdout_paired": paired,
        "committed_fresh_cascade_f1_macro": committed_f1,
        "replication_minus_committed_cascade_f1": (
            replication_f1 - committed_f1 if committed_f1 is not None else None
        ),
        "publish_beside": {
            "divergence_abs_f1": divergence,
            "expected_acceptable_above": 0.003,
            "note": (
                "LLM verdicts are not bit-reproducible; the committed reference stays "
                "and the replication is published beside it (owner decision)"
            ),
        },
    }
    ci_path = cfg.reports_dir / "llm_cascade_paired_ci.json"
    ci_path.write_text(json.dumps(ci_doc, indent=2) + "\n", encoding="utf-8")

    figure_source = committed if committed is not None else result
    save_json(
        _comparison_figure(figure_source, paired_ci=paired),
        cfg.reports_dir / "figures" / "llm_cascade_comparison.json",
    )
    return result
