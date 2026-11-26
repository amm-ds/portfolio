"""Figure builders: smoke tests with tiny inputs (no model artifacts needed)."""

import base64
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from nlp_classification.evaluate import (
    confusion_matrix_figure,
    eda_class_balance_figure,
    error_analysis,
    error_analysis_markdown,
    per_class_f1_comparison_figure,
    training_curve_figure,
)
from nlp_classification.model import TrainingHistory
from nlp_classification.shims import Dataset

CLASS_NAMES = ["World", "Sports", "Business", "Sci/Tech"]


def test_confusion_matrix_figure_smoke() -> None:
    y_true = [0, 1, 2, 3, 0, 1]
    y_pred = [0, 1, 2, 2, 0, 3]
    fig = confusion_matrix_figure(y_true, y_pred, ["a", "b", "c", "d"], "cm", "takeaway")
    assert len(fig.data) == 1
    assert list(fig.data[0].z[0]) == [2, 0, 0, 0]  # class 'a': 2 correct


def test_training_curve_figure_from_history() -> None:
    history = TrainingHistory.from_records(
        [
            {
                "epoch": 1,
                "train_loss": 1.2,
                "val_loss": 1.1,
                "val_f1_macro": 0.4,
                "learning_rate": 1e-5,
            },
            {
                "epoch": 2,
                "train_loss": 0.6,
                "val_loss": 0.8,
                "val_f1_macro": 0.7,
                "learning_rate": 0.0,
            },
        ]
    )
    fig = training_curve_figure(history)
    assert len(fig.data) == 3  # train loss, val loss, val macro-F1
    assert list(fig.data[0].y) == [1.2, 0.6]


def test_eda_class_balance_figure(tiny_dataset: Dataset) -> None:
    fig = eda_class_balance_figure(tiny_dataset, tiny_dataset, tiny_dataset, CLASS_NAMES)
    assert len(fig.data) == 4  # 3 class-count bars + 1 length histogram
    # balanced fixture: every class counts for the full 200-row train split
    train_counts = list(fig.data[0].y)
    assert train_counts == [50, 50, 50, 50]


def test_per_class_f1_comparison_figure() -> None:
    y_true = [0, 1, 2, 3, 0, 1, 2, 3]
    y_sel = [0, 1, 2, 3, 0, 1, 2, 2]
    y_base = [0, 1, 2, 2, 0, 1, 3, 2]
    fig = per_class_f1_comparison_figure(y_true, y_sel, y_base, CLASS_NAMES)
    assert len(fig.data) == 2
    assert all(0.0 <= v <= 1.0 for v in fig.data[0].y)
    # selected: classes 0/1 perfect, class 2 has one false positive, class 3 one miss
    assert list(fig.data[0].y) == pytest.approx([1.0, 1.0, 0.8, 2 / 3])


def test_error_analysis_quotes_most_confused_pair() -> None:
    y_true = [0, 0, 0, 1, 2, 3]
    y_pred = [1, 1, 1, 1, 2, 3]  # class 0 → 1 is the dominant confusion
    texts = [f"headline {i}" for i in range(6)]
    analysis = error_analysis(y_true, y_pred, texts, CLASS_NAMES, n_examples=2)
    assert analysis["true_class"] == "World"
    assert analysis["predicted_class"] == "Sports"
    assert analysis["n_confusions"] == 3
    assert analysis["examples"] == ["headline 0", "headline 1"]
    md = error_analysis_markdown(analysis)
    assert "| World | Sports | 3 |" in md


def _decode(arr: Any) -> Any:
    """Plotly 6 binary arrays ({"bdata": ..., "dtype": ...}) back to lists."""
    if isinstance(arr, dict) and "bdata" in arr:
        raw = base64.b64decode(arr["bdata"])
        fmt = {
            "f8": "d",
            "f4": "f",
            "i8": "q",
            "i4": "i",
            "u8": "Q",
            "u4": "I",
            "i2": "h",
            "u2": "H",
            "i1": "b",
            "u1": "B",
        }[arr.get("dtype", "f8")]
        return list(struct.unpack(f"<{len(raw) // struct.calcsize(fmt)}{fmt}", raw))
    return arr


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed figure payloads (patched without a full re-run) must agree
    with the numbers in their own traces and committed report JSONs."""
    reports = Path(__file__).parents[1] / "reports"
    figures = reports / "figures"

    cascade = json.loads((figures / "llm_cascade_comparison.json").read_text())
    title = cascade["layout"]["title"]["text"]
    base = next(t for t in cascade["data"] if t["name"] == "transformer")
    routed = next(t for t in cascade["data"] if t["name"] == "transformer + selective Kimi review")
    fresh = base["x"].index("fresh holdout")
    cascade_report = json.loads((reports / "llm_cascade.json").read_text())
    n_reviews = cascade_report["fresh holdout"]["n_reviews"]
    assert f"Reviewing {n_reviews} uncertain items" in title
    assert f"{base['y'][fresh]:.4f} → {routed['y'][fresh]:.4f}" in title

    cm = json.loads((figures / "confusion_matrix_selected.json").read_text())
    title = cm["layout"]["title"]["text"]
    heat = cm["data"][0]
    labels = heat["x"]
    flat = _decode(heat["z"])
    n = len(labels)
    z = [flat[i * n : (i + 1) * n] for i in range(n)]
    off_diag = [(z[i][j], i, j) for i in range(n) for j in range(n) if i != j]
    count, true_i, pred_i = max(off_diag)
    assert f"{labels[true_i]} read as {labels[pred_i]} is the largest error" in title
    assert f"({count} of {sum(z[true_i])})" in title

    pc = json.loads((figures / "per_class_f1_comparison.json").read_text())
    title = pc["layout"]["title"]["text"]
    sel = next(t for t in pc["data"] if t["name"] == "selected")
    baseline = next(t for t in pc["data"] if t["name"] == "tf-idf baseline")
    f1_sel, f1_base = _decode(sel["y"]), _decode(baseline["y"])
    assert all(s > b for s, b in zip(f1_sel, f1_base, strict=True))
    assert "beats TF-IDF on every topic" in title
    low = sorted(range(len(f1_sel)), key=lambda i: f1_sel[i])[:2]
    assert f"{sel['x'][low[0]]} and {sel['x'][low[1]]} stay lowest" in title

    hpo = json.loads((figures / "hpo_history.json").read_text())
    title = hpo["layout"]["title"]["text"]
    trials = next(t for t in hpo["data"] if t["name"] == "trial value")
    best = next(t for t in hpo["data"] if t["name"] == "best so far")
    values = _decode(trials["y"])
    assert f"{len(trials['x'])} trials" in title
    assert f"best validation macro-F1 {max(_decode(best['y'])):.4f}" in title
    seeds = json.loads((reports / "hpo_seeds.json").read_text())
    assert seeds["std"] > max(values) - sorted(values)[-2]  # seed-noise clause
    assert "not separated from seed noise" in title

    eda = json.loads((figures / "eda_class_balance.json").read_text())
    title = eda["layout"]["title"]["text"]
    bars = [t for t in eda["data"] if t["type"] == "bar"]
    assert len(bars[0]["x"]) == 4 and "Four topics" in title
    assert all(len(set(_decode(t["y"]))) == 1 for t in bars)  # equal class sizes
    assert "equal class sizes" in title
    hist = next(t for t in eda["data"] if t["type"] == "histogram")
    word_counts = np.array(_decode(hist["x"]), dtype=float)
    under = int(np.ceil(np.percentile(word_counts, 90) / 10.0) * 10)
    assert (word_counts < under).mean() >= 0.9
    assert f"most items under {under} words" in title

    curve = json.loads((figures / "training_curve.json").read_text())
    title = curve["layout"]["title"]["text"]
    f1_traces = [t for t in curve["data"] if t.get("name") == "val macro-F1"]
    headline = max(_decode(next(t for t in f1_traces if len(t["x"]) == 2)["y"]))
    probe = max(_decode(next(t for t in f1_traces if len(t["x"]) == 4)["y"]))
    assert f"Extra epochs add {probe - headline:+.4f} val macro-F1" in title
    assert f"{probe:.4f} probe peak vs {headline:.4f} headline" in title
