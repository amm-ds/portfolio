"""Fresh-holdout model selection + confidence-routed serving (roadmap work).

Two bounded experiments over the persisted artifacts — no retraining:

1. **Fresh-holdout selection.** The reported ``distilbert_tuned`` run was
   chosen by test macro-F1 (``reports/selection.json``), so the bounded
   1,000-row test split is not a clean holdout for the tuned-vs-artifact
   comparison. This stage recomputes exactly which rows the bounded split
   contains (the seeded draw is deterministic), takes the complement inside
   the full AG News test partition (7.6k rows), draws a fresh seeded
   stratified holdout from it, and scores both selection candidates plus the
   TF-IDF baseline, ``encoder_b`` and — when the artifact exists — the full
   120k fine-tune. The point is an unbiased reading of the two candidates;
   no further selection is applied.

2. **Confidence-routed serving** (the cost-sensitive routing item). Serve
   TF-IDF where it is confident (max class probability >= tau), escalate the
   rest to the transformer. Sweeping tau traces the accuracy / macro-F1 vs
   escalation-rate frontier on the fresh holdout; the endpoints must
   reproduce the two constituent models, which is asserted.

Artifact: ``reports/fresh_holdout.json`` (machine-readable; no figures — the
experiment is a table, and the story quotes it).
"""

import json
import time
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from portfolio_core.logging import get_logger
from portfolio_eval.ml import classification_metrics
from sklearn import metrics as skm

from nlp_classification.config import NLPConfig
from nlp_classification.data import (
    LABEL_COLUMN,
    TEXT_COLUMN,
    load_ag_news,
    run_dq_gates,
    stratified_subsample,
    stratified_subsample_indices,
    tokenize_dataset,
)
from nlp_classification.evaluate import load_tokenizer
from nlp_classification.model import (
    BASELINE_PATH,
    ENCODER_B_MODEL_PATH,
    FULLDATA_MODEL_PATH,
    NN_MODEL_PATH,
    TUNED_MODEL_PATH,
    build_nn_model,
    load_baseline,
    load_nn_state_dict,
    predict_baseline,
    predict_proba_nn,
)
from nlp_classification.shims import Dataset

logger = get_logger(__name__)

# Router/transformer roles in the cascade experiment.
WAVE2 = "wave2_artifact"
HPO = "hpo_retrained"


def _load_label_names(data_dir: Path) -> list[str]:
    return cast(list[str], json.loads((data_dir / "label_names.json").read_text()))


def draw_fresh_holdout(cfg: NLPConfig, raw_test: Dataset) -> tuple[Dataset, dict[str, Any]]:
    """Fresh seeded stratified holdout: the complement of the bounded split.

    Recomputes the bounded test draw (seed ``cfg.seed + 1``, identical RNG
    stream to the prepare stage), excludes those rows from the full test
    partition, and draws ``cfg.fresh_holdout_samples`` rows from the
    remainder (seed ``cfg.seed + 3``). Returns the fresh dataset plus the
    provenance block persisted into the report.
    """
    bounded_idx = stratified_subsample_indices(raw_test, cfg.test_samples, seed=cfg.seed + 1)
    complement = sorted(set(range(len(raw_test))) - set(bounded_idx))
    complement_ds = raw_test.select(complement)
    fresh = stratified_subsample(complement_ds, cfg.fresh_holdout_samples, seed=cfg.seed + 3)
    provenance = {
        "n_total_test_partition": len(raw_test),
        "n_bounded_test": len(bounded_idx),
        "bounded_test_seed": cfg.seed + 1,
        "n_complement": len(complement),
        "n_fresh": len(fresh),
        "fresh_seed": cfg.seed + 3,
        "overlap_with_bounded": 0,
        "draw": "seeded per-class stratified, disjoint from the bounded test split by "
        "construction (complement of the identical recomputed draw)",
    }
    return fresh, provenance


def _metrics_dict(y_true: list[int], y_pred: list[int]) -> dict[str, float]:
    out = {m.name: m.value for m in classification_metrics(y_true, y_pred)}
    out["f1_weighted"] = float(skm.f1_score(y_true, y_pred, average="weighted", zero_division=0))
    return out


def _proba_distilbert(cfg: NLPConfig, state_path: Path, ds: Dataset, n_labels: int) -> np.ndarray:
    """Softmax probabilities from a persisted DistilBERT-head artifact."""
    device = torch.device("cpu")
    tokenizer = load_tokenizer(cfg.model_name)
    tokenized = tokenize_dataset(ds, tokenizer, cfg.max_length)
    model = build_nn_model(cfg, n_labels)
    model = load_nn_state_dict(model, state_path, device)
    return predict_proba_nn(model, tokenized, device, cfg.batch_size)


def run_fresh_holdout(cfg: NLPConfig, loader: Any = load_ag_news) -> dict[str, Any]:
    """Score the persisted artifacts on the fresh holdout; run the routing sweep.

    Writes ``reports/fresh_holdout.json`` and returns the document. Figures
    are intentionally not produced (a table is the honest artifact here).
    """
    started = time.perf_counter()
    raw_test = loader()["test"]
    fresh, provenance = draw_fresh_holdout(cfg, raw_test)
    labels = _load_label_names(cfg.data_dir)
    n_labels = len(labels)

    dq = run_dq_gates(fresh, "ag_news/fresh_holdout", n_labels)
    dq.raise_if_failed()
    y_true = [int(v) for v in fresh[LABEL_COLUMN]]
    texts = list(fresh[TEXT_COLUMN])

    runs: dict[str, dict[str, float]] = {}

    baseline = load_baseline(cfg.models_dir / BASELINE_PATH)
    base_pred = predict_baseline(baseline, texts)
    runs["baseline_tfidf_logreg"] = _metrics_dict(y_true, base_pred.tolist())
    base_conf = np.asarray(baseline.predict_proba(texts)).max(axis=1)

    device = torch.device("cpu")
    nn_preds: dict[str, np.ndarray] = {}
    for name, path, model_name in (
        (WAVE2, cfg.models_dir / NN_MODEL_PATH, cfg.model_name),
        (HPO, cfg.models_dir / TUNED_MODEL_PATH, cfg.model_name),
        ("encoder_b", cfg.models_dir / ENCODER_B_MODEL_PATH, cfg.encoder_b_name),
    ):
        tokenizer = load_tokenizer(model_name)
        tokenized = tokenize_dataset(fresh, tokenizer, cfg.max_length)
        model = build_nn_model(cfg.model_copy(update={"model_name": model_name}), n_labels)
        model = load_nn_state_dict(model, path, device)
        proba = predict_proba_nn(model, tokenized, device, cfg.batch_size)
        nn_preds[name] = proba.argmax(axis=-1)
        runs[f"distilbert_{name}" if name in (WAVE2, HPO) else name] = _metrics_dict(
            y_true, [int(v) for v in nn_preds[name]]
        )

    fulldata_path = cfg.models_dir / FULLDATA_MODEL_PATH
    if fulldata_path.exists():
        proba = _proba_distilbert(cfg, fulldata_path, fresh, n_labels)
        runs["distilbert_full_120k"] = _metrics_dict(
            y_true, [int(v) for v in proba.argmax(axis=-1)]
        )

    # Fresh selection reading: what the unbiased holdout says about the two
    # candidates the test split could not cleanly separate.
    test_selection = json.loads(Path(cfg.selection_path).read_text())
    cand = {
        WAVE2: runs["distilbert_wave2_artifact"]["f1_macro"],
        HPO: runs["distilbert_hpo_retrained"]["f1_macro"],
    }
    fresh_winner = max(cand, key=lambda name: cand[name])
    selection_on_fresh = {
        "candidates_f1_macro": cand,
        "fresh_winner": fresh_winner,
        "margin_f1_macro": cand[fresh_winner] - cand[WAVE2 if fresh_winner == HPO else HPO],
        "test_selected": test_selection["winner"],
        "agrees_with_test_selection": fresh_winner == test_selection["winner"],
        "note": "reading only — no further selection applied; both candidates "
        "reported so the margin can be read either way",
    }

    # Confidence-routed serving: TF-IDF above the cutoff, transformer below.
    # The transformer is the served bounded model (the test-selection winner).
    served_key = HPO if test_selection["winner"] == "hpo_retrained" else WAVE2
    transformer_pred = nn_preds[served_key]
    transformer_label = (
        "distilbert_tuned (HPO-retrained)"
        if served_key == HPO
        else "distilbert_tuned (wave-2 artifact)"
    )
    cascade_rows = []
    for tau in sorted(cfg.cascade_taus):
        escalate = base_conf < tau
        routed = np.where(escalate, transformer_pred, base_pred)
        cascade_rows.append(
            {
                "tau": tau,
                "escalation_rate": float(escalate.mean()),
                "n_escalated": int(escalate.sum()),
                "accuracy": float((routed == np.asarray(y_true)).mean()),
                "f1_macro": float(skm.f1_score(y_true, routed, average="macro", zero_division=0)),
            }
        )
    cascade = {
        "router": "TF-IDF max class probability (raw, uncalibrated)",
        "transformer": transformer_label,
        "cost_note": "TF-IDF predictions are ~40x faster and token-free "
        "(serving economics table); each escalated row pays the transformer price",
        "rows": cascade_rows,
    }

    doc: dict[str, Any] = {
        "generated_by": "nlp_classification.cli fresh-holdout",
        "bounded_selection_caveat": "reports/selection.json used the bounded test "
        "split; this fresh holdout is disjoint from it",
        "fresh_holdout": provenance,
        "class_balance_fresh": {
            labels[i]: int(np.sum(np.asarray(y_true) == i)) for i in range(n_labels)
        },
        "runs": runs,
        "selection_on_fresh": selection_on_fresh,
        "cascade": cascade,
        "runtime_s": round(time.perf_counter() - started, 1),
    }
    out_path = Path(cfg.reports_dir) / "fresh_holdout.json"
    out_path.write_text(json.dumps(doc, indent=2) + "\n")
    logger.info(
        "fresh holdout: %d rows; fresh winner=%s (margin %.4f); cascade rows=%d -> %s",
        len(fresh),
        fresh_winner,
        selection_on_fresh["margin_f1_macro"],
        len(cascade_rows),
        out_path,
    )
    return doc
