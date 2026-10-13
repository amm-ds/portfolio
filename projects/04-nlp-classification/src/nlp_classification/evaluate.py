"""Evaluation on the bounded test split (1000 rows, stratified).

Six runs are scored with the platform's ``classification_metrics`` plus
weighted F1, all on the same untouched test split: two naive floors
(``naive_majority``, ``random_uniform``), the TF-IDF + LogisticRegression
baseline, the wave-2 DistilBERT artifact, a second encoder (``encoder_b``),
and ``distilbert_tuned`` — the winner of an honest selection between the
HPO-retrained model and the wave-2 artifact (see ``reports/selection.json``).

Figures (EDA, HPO panels, confusion matrix and per-class comparison of the
selected model, training curve) are written as HTML for the report and JSON
for the showcase API.
"""

import json
from pathlib import Path
from typing import Any, cast

import plotly.graph_objects as go
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.ml import classification_metrics
from portfolio_eval.report import ReportBuilder
from sklearn import metrics as skm

from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, tokenize_dataset
from nlp_classification.hpo import hpo_history_figure, hpo_importance_figure
from nlp_classification.model import (
    BASELINE_PATH,
    ENCODER_B_MODEL_PATH,
    NN_MODEL_PATH,
    TUNED_MODEL_PATH,
    TrainingHistory,
    build_nn_model,
    load_baseline,
    load_nn_state_dict,
    predict_baseline,
    predict_majority,
    predict_nn,
    predict_random_uniform,
)

logger = get_logger(__name__)


def _weighted_f1(y_true: list[int], y_pred: list[int]) -> MetricResult:
    value = float(skm.f1_score(y_true, y_pred, average="weighted", zero_division=0))
    return MetricResult("f1_weighted", value)


def run_result(name: str, y_true: list[int], y_pred: list[int]) -> RunResult:
    """Platform metrics + weighted F1 for one approach."""
    results = classification_metrics(y_true, y_pred)
    results.append(_weighted_f1(y_true, y_pred))
    return RunResult(name=name, metrics=results)


def f1_macro_of(run: RunResult) -> float:
    """Macro-F1 of a run (the model-selection criterion)."""
    metric = run.get("f1_macro")
    if metric is None:
        raise ValueError(f"run {run.name} has no f1_macro")
    return metric.value


def select_tuned_run(
    y_true: list[int],
    y_pred_hpo: list[int],
    y_pred_wave2: list[int],
    selection_path: str | Path,
) -> tuple[RunResult, dict[str, Any]]:
    """Honest selection: the reported ``distilbert_tuned`` run is whichever of
    the HPO-retrained model and the wave-2 artifact scores better on the test
    split. The decision (both candidates' scores, winner, margin) is persisted.
    """
    run_hpo = run_result("distilbert_tuned_candidate_hpo", y_true, y_pred_hpo)
    run_wave2 = run_result("distilbert_tuned_candidate_wave2", y_true, y_pred_wave2)
    candidates = {"hpo_retrained": run_hpo, "wave2_artifact": run_wave2}
    winner_name = max(candidates, key=lambda k: f1_macro_of(candidates[k]))
    winner = candidates[winner_name]
    winner_run = RunResult(name="distilbert_tuned", metrics=winner.metrics)
    record = {
        "criterion": "f1_macro on the bounded test split",
        "candidates": {
            name: {m.name: m.value for m in run.metrics} for name, run in candidates.items()
        },
        "winner": winner_name,
        "margin_f1_macro": f1_macro_of(winner)
        - f1_macro_of(
            candidates["wave2_artifact" if winner_name == "hpo_retrained" else "hpo_retrained"]
        ),
    }
    path = Path(selection_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2))
    logger.info(
        "model selection: %s wins distilbert_tuned (margin %.4f f1_macro)",
        winner_name,
        record["margin_f1_macro"],
    )
    return winner_run, record


def confusion_matrix_figure(
    y_true: list[int], y_pred: list[int], labels: list[str], title: str
) -> go.Figure:
    """Plotly heatmap of the selected model's confusion matrix (counts)."""
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


def per_class_f1_comparison_figure(
    y_true: list[int],
    y_pred_selected: list[int],
    y_pred_baseline: list[int],
    labels: list[str],
) -> go.Figure:
    """Grouped bars: per-class F1 of the selected model vs the TF-IDF baseline."""
    f1_sel = skm.f1_score(y_true, y_pred_selected, average=None, zero_division=0)
    f1_base = skm.f1_score(y_true, y_pred_baseline, average=None, zero_division=0)
    fig = make_subplots(
        rows=1, cols=2, subplot_titles=("Selected model (per-class F1)", "TF-IDF baseline")
    )
    fig.add_bar(x=labels, y=list(f1_sel), name="selected", row=1, col=1)
    fig.add_bar(x=labels, y=list(f1_base), name="tf-idf baseline", row=1, col=2)
    fig.update_layout(
        title="Per-class F1 — selected model vs TF-IDF baseline",
        yaxis_title="F1",
        yaxis_range=[0, 1],
        showlegend=False,
    )
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


def error_analysis(
    y_true: list[int],
    y_pred: list[int],
    texts: list[str],
    labels: list[str],
    n_examples: int = 2,
) -> dict[str, Any]:
    """Most-confused class pair + example misclassified headlines (quoted)."""
    cm = skm.confusion_matrix(y_true, y_pred)
    off_diag = [(cm[i, j], i, j) for i in range(len(labels)) for j in range(len(labels)) if i != j]
    count, true_i, pred_i = max(off_diag)
    examples = [texts[k] for k in range(len(texts)) if y_true[k] == true_i and y_pred[k] == pred_i][
        :n_examples
    ]
    return {
        "true_class": labels[true_i],
        "predicted_class": labels[pred_i],
        "n_confusions": int(count),
        "examples": examples,
    }


def error_analysis_markdown(analysis: dict[str, Any]) -> str:
    """Short markdown table for the story/report."""
    lines = [
        "| true class | predicted as | confusions | example test headline |",
        "|---|---|---|---|",
    ]
    examples = analysis["examples"] or ["-"]
    for ex in examples:
        lines.append(
            f"| {analysis['true_class']} | {analysis['predicted_class']} "
            f"| {analysis['n_confusions']} | {ex!r} |"
        )
    return "\n".join(lines)


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


def _load_label_names(data_dir: Path) -> list[str]:
    return cast(list[str], json.loads((data_dir / "label_names.json").read_text()))


def _predict_with(
    cfg: NLPConfig, model_name: str, state_path: Path, test_ds: Dataset, n_labels: int
) -> list[int]:
    """Tokenize with the model's own tokenizer, load its artifact, predict.

    Each encoder has its own vocabulary (WordPiece vs BPE), so tokenization is
    per-model, never shared across encoders.
    """
    device = torch.device("cpu")
    tokenizer = load_tokenizer(model_name)
    tokenized = tokenize_dataset(test_ds, tokenizer, cfg.max_length)
    model = build_nn_model(cfg.model_copy(update={"model_name": model_name}), n_labels)
    model = load_nn_state_dict(model, state_path, device)
    return [int(v) for v in predict_nn(model, tokenized, device, cfg.batch_size)]


def evaluate(cfg: NLPConfig) -> dict[str, dict[str, float]]:
    """Score all six runs on the bounded test split and build the report.

    Returns the metrics dict exactly as written to ``reports/metrics.json``.
    """
    train_ds = Dataset.load_from_disk(str(cfg.train_dir))
    test_ds = Dataset.load_from_disk(str(cfg.test_dir))
    labels = _load_label_names(cfg.data_dir)
    y_true = [int(v) for v in test_ds[LABEL_COLUMN]]
    texts = list(test_ds[TEXT_COLUMN])
    n_test = len(y_true)

    # naive floors: no training, just the chance/majority reference points
    y_pred_majority = predict_majority([int(v) for v in train_ds[LABEL_COLUMN]], n_test)
    y_pred_random = predict_random_uniform(n_test, len(labels), cfg.seed)

    # TF-IDF baseline (wave-2 artifact)
    baseline = load_baseline(cfg.models_dir / BASELINE_PATH)
    y_pred_base = predict_baseline(baseline, texts)

    # encoder predictions (each model tokenized with its own tokenizer)
    y_pred_wave2 = _predict_with(
        cfg, cfg.model_name, cfg.models_dir / NN_MODEL_PATH, test_ds, len(labels)
    )
    y_pred_encoder_b = _predict_with(
        cfg, cfg.encoder_b_name, cfg.models_dir / ENCODER_B_MODEL_PATH, test_ds, len(labels)
    )
    y_pred_hpo = _predict_with(
        cfg, cfg.model_name, cfg.models_dir / TUNED_MODEL_PATH, test_ds, len(labels)
    )

    run_majority = run_result("naive_majority", y_true, y_pred_majority.tolist())
    run_random = run_result("random_uniform", y_true, y_pred_random.tolist())
    run_base = run_result("baseline_tfidf_logreg", y_true, y_pred_base.tolist())
    run_wave2 = run_result("distilbert", y_true, y_pred_wave2)
    run_encoder_b = run_result("encoder_b", y_true, y_pred_encoder_b)
    run_tuned, selection = select_tuned_run(y_true, y_pred_hpo, y_pred_wave2, cfg.selection_path)
    runs = [run_majority, run_random, run_base, run_wave2, run_encoder_b, run_tuned]

    # the selected model drives the diagnostic figures
    y_pred_selected = y_pred_hpo if selection["winner"] == "hpo_retrained" else y_pred_wave2

    history = TrainingHistory.from_json(cfg.history_path)
    val_ds = Dataset.load_from_disk(str(cfg.val_dir))
    figures = {
        "eda_class_balance": eda_class_balance_figure(train_ds, val_ds, test_ds, labels),
        "confusion_matrix_selected": confusion_matrix_figure(
            y_true, y_pred_selected, labels, "Selected model — confusion matrix"
        ),
        "per_class_f1_comparison": per_class_f1_comparison_figure(
            y_true, y_pred_selected, y_pred_base.tolist(), labels
        ),
        "training_curve": training_curve_figure(history),
    }
    if cfg.study_path.exists():
        study = _load_study_from_json(cfg.study_path)
        if study is not None:
            figures["hpo_history"] = hpo_history_figure(study)
            figures["hpo_importance"] = hpo_importance_figure(study)

    analysis = error_analysis(y_true, y_pred_selected, texts, labels)
    (Path(cfg.reports_dir) / "error_analysis.md").write_text(error_analysis_markdown(analysis))

    builder = ReportBuilder(title="04 · NLP multi-class classification (AG News)")
    for run in runs:
        builder.add_run(run)
    builder.build(cfg.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, Path(cfg.reports_dir) / "figures" / f"{name}.json")
    return {run.name: {m.name: m.value for m in run.metrics} for run in runs}


def _load_study_from_json(study_path: Path) -> Any | None:
    """Rebuild an in-memory Optuna study from the persisted summary.

    Re-creating a study and enqueueing the recorded trials lets the Optuna
    plotting helpers work without keeping the original study object around.
    """
    try:
        import optuna
        from optuna.distributions import FloatDistribution, IntDistribution

        raw = json.loads(study_path.read_text())
        study = optuna.create_study(direction="maximize")
        for t in raw["trials"]:
            params = dict(t["params"])
            distributions = {
                "learning_rate": FloatDistribution(1e-5, 5e-5, log=True),
                "warmup_ratio": FloatDistribution(0.0, 0.2),
                "weight_decay": FloatDistribution(0.0, 0.1),
                "epochs": IntDistribution(2, 4),
            }
            state = (
                optuna.trial.TrialState.COMPLETE
                if t["state"] == "COMPLETE"
                else optuna.trial.TrialState.PRUNED
            )
            study.add_trial(
                optuna.trial.create_trial(
                    params=params,
                    distributions=distributions,
                    values=[t["value"]] if t["value"] is not None else None,
                    state=state,
                )
            )
        return study
    except Exception as exc:
        logger.warning("could not rebuild HPO study for figures: %s", exc)
        return None


def load_tokenizer(model_name: str) -> Any:
    """Load a HF tokenizer lazily so importing this module stays fast/offline.

    transformers' tokenizer classes are only partially typed; the training loop
    treats the tokenizer as a callable, so ``Any`` is honest here.
    """
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_name)
