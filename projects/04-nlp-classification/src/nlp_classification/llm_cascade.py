"""Leakage-safe selective LLM review for the strongest transformer artifact.

The threshold is fitted only on validation predictions. Test and fresh-holdout
labels are used solely for final metrics, never for routing or prompt content.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol, cast

import numpy as np
import plotly.graph_objects as go
import torch
from portfolio_core.config import get_settings
from portfolio_core.llm import build_model, hosted_model_settings, is_hosted_provider
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from sklearn import metrics as skm

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, load_ag_news, tokenize_dataset
from nlp_classification.evaluate import load_tokenizer
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

    def review(self, texts: list[str], indices: list[int]) -> dict[int, ReviewDecision]: ...


class KimiReviewer:
    """Structured eight-row review through the platform's configured provider."""

    def __init__(self, label_names: list[str]) -> None:
        self.label_names = label_names
        self.input_tokens = 0
        self.output_tokens = 0
        self.latency_s = 0.0
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


def apply_threshold(
    probas: np.ndarray, texts: list[str], threshold: float, reviewer: Reviewer
) -> np.ndarray:
    """Route only sub-threshold rows to the reviewer and return final labels."""
    confidence = probas.max(axis=1)
    indices = [i for i, conf in enumerate(confidence) if conf < threshold]
    routed = probas.argmax(axis=1)
    for index, decision in reviewer.review(texts, indices).items():
        routed[index] = decision.label_index
    return routed


def _predict_full(cfg: NLPConfig, dataset: Dataset, n_labels: int) -> np.ndarray:
    device = torch.device("cpu")
    tokenizer = load_tokenizer(cfg.model_name)
    tokenized = tokenize_dataset(dataset, tokenizer, cfg.max_length)
    model = build_nn_model(cfg, n_labels)
    model = load_nn_state_dict(model, cfg.models_dir / FULLDATA_MODEL_PATH, device)
    return predict_proba_nn(model, tokenized, device, cfg.batch_size)


def _label_names(cfg: NLPConfig) -> list[str]:
    return cast(list[str], json.loads((cfg.data_dir / "label_names.json").read_text()))


def _comparison_figure(result: dict[str, Any]) -> go.Figure:
    labels = ["validation", "bounded test", "fresh holdout"]
    baseline = [result[split]["baseline_f1_macro"] for split in labels]
    cascade = [result[split]["cascade_f1_macro"] for split in labels]
    fig = go.Figure()
    fig.add_bar(x=labels, y=baseline, name="transformer")
    fig.add_bar(x=labels, y=cascade, name="transformer + selective Kimi review")
    fig.update_layout(
        title="Selective review — frozen threshold, final scores",
        barmode="group",
        yaxis_title="macro-F1",
        yaxis_range=[0, 1],
    )
    add_takeaway(fig, "threshold fitted on validation only; test and fresh holdout are scored once")
    return apply_theme(fig)


def run_cascade(
    cfg: NLPConfig, *, reviewer: Reviewer | None = None, loader: Any = load_ag_news
) -> dict[str, Any]:
    """Fit validation routing, score test/fresh once, and persist the full verdict."""
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
    for split, ds, probas in (
        ("validation", val_ds, val_proba),
        ("bounded test", test_ds, test_proba),
        ("fresh holdout", fresh, fresh_proba),
    ):
        y_true = [int(v) for v in ds[LABEL_COLUMN]]
        baseline = probas.argmax(axis=1)
        routed = apply_threshold(probas, list(ds[TEXT_COLUMN]), threshold, resolved_reviewer)
        result[split] = {
            "baseline_f1_macro": _f1(y_true, baseline),
            "cascade_f1_macro": _f1(y_true, routed),
            "baseline_accuracy": float((baseline == np.asarray(y_true)).mean()),
            "cascade_accuracy": float((routed == np.asarray(y_true)).mean()),
            "n_reviews": int((probas.max(axis=1) < threshold).sum()),
        }

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
    }
    path = cfg.reports_dir / "llm_cascade.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    save_json(
        _comparison_figure(result), cfg.reports_dir / "figures" / "llm_cascade_comparison.json"
    )
    return result
