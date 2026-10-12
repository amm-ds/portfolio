"""Evaluation on the bounded test split (1000 rows, stratified).

Four runs are scored with the platform's ``classification_metrics`` plus
weighted F1: two naive floors (majority class, seeded uniform random), the
TF-IDF + LogisticRegression baseline, and the fine-tuned DistilBERT. Figures
(EDA, confusion heatmap, per-class F1, training curve) are written as HTML for
the report and JSON for the showcase API.
"""

import json
from pathlib import Path
from typing import Any, cast

import plotly.graph_objects as go
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from plotly.subplots import make_subplots
from portfolio_core.plotting import apply_theme, save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.ml import classification_metrics
from portfolio_eval.report import ReportBuilder
from sklearn import metrics as skm

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, tokenize_dataset
from nlp_classification.model import (
    BASELINE_PATH,
    NN_MODEL_PATH,
    TrainingHistory,
    build_nn_model,
    load_baseline,
    load_nn_state_dict,
    predict_baseline,
    predict_majority,
    predict_nn,
    predict_random_uniform,
)


def _weighted_f1(y_true: list[int], y_pred: list[int]) -> MetricResult:
    value = float(skm.f1_score(y_true, y_pred, average="weighted", zero_division=0))
    return MetricResult("f1_weighted", value)


def run_result(name: str, y_true: list[int], y_pred: list[int]) -> RunResult:
    """Platform metrics + weighted F1 for one approach."""
    results = classification_metrics(y_true, y_pred)
    results.append(_weighted_f1(y_true, y_pred))
    return RunResult(name=name, metrics=results)


def confusion_matrix_figure(
    y_true: list[int], y_pred: list[int], labels: list[str], title: str
) -> go.Figure:
    """Plotly heatmap of the fine-tuned model's confusion matrix (counts)."""
    cm = skm.confusion_matrix(y_true, y_pred)
    fig = go.Figure(
        data=go.Heatmap(
            z=cm,
            x=labels,
            y=labels,
            text=cm,
            texttemplate="%{text}",
            colorscale="Teal",
        )
    )
    fig.update_layout(title=title, xaxis_title="predicted", yaxis_title="true")
    return apply_theme(fig)


def per_class_f1_figure(
    y_true: list[int], y_pred: list[int], labels: list[str], title: str
) -> go.Figure:
    """Bar chart of per-class F1 for the fine-tuned model."""
    f1s = skm.f1_score(y_true, y_pred, average=None, zero_division=0)
    fig = go.Figure(data=go.Bar(x=labels, y=list(f1s)))
    fig.update_layout(title=title, yaxis_title="F1", yaxis_range=[0, 1])
    return apply_theme(fig)


def training_curve_figure(history: TrainingHistory) -> go.Figure:
    """Train/val loss and validation macro-F1 across epochs."""
    epochs = [e.epoch for e in history.epochs]
    fig = go.Figure()
    fig.add_scatter(x=epochs, y=[e.train_loss for e in history.epochs], name="train loss")
    fig.add_scatter(x=epochs, y=[e.val_loss for e in history.epochs], name="val loss")
    fig.add_scatter(x=epochs, y=[e.val_f1_macro for e in history.epochs], name="val macro-F1")
    fig.update_layout(
        title="Hand-written loop: losses and validation macro-F1",
        xaxis_title="epoch",
        yaxis_title="value",
    )
    return apply_theme(fig)


def _load_label_names(data_dir: Path) -> list[str]:
    return cast(list[str], json.loads((data_dir / "label_names.json").read_text()))


def eda_class_balance_figure(
    train_ds: Dataset, val_ds: Dataset, test_ds: Dataset, labels: list[str]
) -> go.Figure:
    """Class distribution across the bounded splits + train text-length histogram.

    Computed from the persisted prepared data — no re-download. Text length is
    measured in words (standard for short-news headlines + descriptions).
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Class distribution (bounded subsample)", "Train text length (words)"),
    )
    for split_name, ds in (("train", train_ds), ("val", val_ds), ("test", test_ds)):
        y = [int(ds[LABEL_COLUMN].count(i)) for i in range(len(labels))]
        fig.add_bar(x=labels, y=y, name=split_name, row=1, col=1)
    word_counts = [len(t.split()) for t in train_ds[TEXT_COLUMN]]
    fig.add_histogram(x=word_counts, name="train", row=1, col=2)
    fig.update_layout(
        title="AG News bounded subsample — class balance and text lengths",
        barmode="group",
        xaxis_title="class",
        yaxis_title="rows",
        xaxis2_title="words per text",
        yaxis2_title="rows",
    )
    return apply_theme(fig)


def evaluate(cfg: NLPConfig) -> dict[str, dict[str, float]]:
    """Score all runs on the bounded test split and build the report.

    Runs (same 1000-row stratified test split for each): ``naive_majority``,
    ``random_uniform``, ``baseline_tfidf_logreg``, ``distilbert_finetuned``.
    Returns the metrics dict exactly as written to ``reports/metrics.json``.
    """
    train_ds = Dataset.load_from_disk(str(cfg.train_dir))
    test_ds = Dataset.load_from_disk(str(cfg.test_dir))
    labels = _load_label_names(cfg.data_dir)
    y_true = [int(v) for v in test_ds[LABEL_COLUMN]]
    n_test = len(y_true)

    # naive floors: no training, just the chance/majority reference points
    y_pred_majority = predict_majority([int(v) for v in train_ds[LABEL_COLUMN]], n_test)
    y_pred_random = predict_random_uniform(n_test, len(labels), cfg.seed)

    # (a) sklearn baseline predictions
    baseline = load_baseline(cfg.models_dir / BASELINE_PATH)
    y_pred_base = predict_baseline(baseline, list(test_ds[TEXT_COLUMN]))

    # (b) fine-tuned DistilBERT predictions
    device = torch.device("cpu")
    tokenizer = load_tokenizer(cfg.model_name)
    tokenized = tokenize_dataset(test_ds, tokenizer, cfg.max_length)
    model = build_nn_model(cfg, len(labels))
    model = load_nn_state_dict(model, cfg.models_dir / NN_MODEL_PATH, device)
    y_pred_nn = predict_nn(model, tokenized, device, cfg.batch_size)

    run_majority = run_result("naive_majority", y_true, y_pred_majority.tolist())
    run_random = run_result("random_uniform", y_true, y_pred_random.tolist())
    run_base = run_result("baseline_tfidf_logreg", y_true, y_pred_base.tolist())
    run_nn = run_result("distilbert_finetuned", y_true, y_pred_nn.tolist())
    runs = [run_majority, run_random, run_base, run_nn]

    history = TrainingHistory.from_json(cfg.history_path)
    val_ds = Dataset.load_from_disk(str(cfg.val_dir))
    figures = {
        "eda_class_balance": eda_class_balance_figure(train_ds, val_ds, test_ds, labels),
        "confusion_matrix_distilbert": confusion_matrix_figure(
            y_true, y_pred_nn.tolist(), labels, "DistilBERT fine-tuned — confusion matrix"
        ),
        "per_class_f1_distilbert": per_class_f1_figure(
            y_true, y_pred_nn.tolist(), labels, "DistilBERT fine-tuned — per-class F1"
        ),
        "training_curve": training_curve_figure(history),
    }

    builder = ReportBuilder(title="04 · NLP multi-class classification (AG News)")
    for run in runs:
        builder.add_run(run)
    builder.build(cfg.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, Path(cfg.reports_dir) / "figures" / f"{name}.json")
    return {run.name: {m.name: m.value for m in run.metrics} for run in runs}


def load_tokenizer(model_name: str) -> Any:
    """Load a HF tokenizer lazily so importing this module stays fast/offline.

    transformers' tokenizer classes are only partially typed; the training loop
    treats the tokenizer as a callable, so ``Any`` is honest here.
    """
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_name)
