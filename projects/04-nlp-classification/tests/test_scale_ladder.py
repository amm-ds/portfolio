"""Controlled data-scale ladder tests (offline, mocked artifacts).

Covers the rung naming/discovery helpers, the provenance sidecar reader, the
ladder figure builder, and the fresh-holdout inclusion of a persisted rung —
without weights, tokenizer, or network (the same monkeypatch pattern as
``test_fresh_holdout.py``).
"""

import json
from pathlib import Path

import numpy as np
import pytest
from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN
from nlp_classification.evaluate import _read_scale_meta, scale_ladder_figure
from nlp_classification.fresh_holdout import run_fresh_holdout
from nlp_classification.model import (
    existing_scale_rungs,
    scaled_history_name,
    scaled_meta_name,
    scaled_model_name,
)
from nlp_classification.shims import ClassLabel, Dataset, DatasetDict, Features, Value

N_CLASSES = 4
NAMES = ["World", "Sports", "Business", "Sci/Tech"]
FEATURES = Features({TEXT_COLUMN: Value("string"), LABEL_COLUMN: ClassLabel(names=NAMES)})


def _rows(n: int) -> dict[str, list[str] | list[int]]:
    return {
        TEXT_COLUMN: [f"{NAMES[i % N_CLASSES]} item {i} words here" for i in range(n)],
        LABEL_COLUMN: [i % N_CLASSES for i in range(n)],
    }


def _cfg(tmp_path: Path) -> NLPConfig:
    return NLPConfig(
        test_samples=100,
        fresh_holdout_samples=100,
        cascade_taus=[0.25, 1.0],  # 0.25 == the fake router's flat confidence
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )


def test_scale_artifact_naming_is_subset_addressed() -> None:
    """Rung artifacts are named by the --subset knob that reproduces them."""
    assert scaled_model_name(12000) == "distilbert_scale_12000.pt"
    assert scaled_history_name(12000) == "history_scale_12000.json"
    assert scaled_meta_name(12000) == "scale_meta_12000.json"
    # per-rung names must never collide with the headline artifacts
    for name in ("distilbert.pt", "distilbert_fulldata.pt", "distilbert_tuned.pt"):
        assert scaled_model_name(12000) != name


def test_scale_ladder_defaults_from_params() -> None:
    cfg = NLPConfig()
    assert cfg.scale_ladder.subsets == [4000, 12000, 40000]


def test_existing_scale_rungs_only_persisted_ascending(tmp_path: Path) -> None:
    cfg = NLPConfig(reports_dir=tmp_path / "reports")
    cfg.models_dir.mkdir(parents=True)
    # 12000 and 40000 artifacts on disk; 4000 never trained
    for subset in (40000, 12000):
        (cfg.models_dir / scaled_model_name(subset)).write_bytes(b"x")
    assert existing_scale_rungs(cfg) == [12000, 40000]
    # no artifacts at all -> no rungs (evaluate/fresh-holdout stay unchanged)
    empty = NLPConfig(reports_dir=tmp_path / "empty")
    empty.models_dir.mkdir(parents=True)
    assert existing_scale_rungs(empty) == []


def test_read_scale_meta_roundtrip(tmp_path: Path) -> None:
    cfg = NLPConfig(reports_dir=tmp_path / "reports")
    assert _read_scale_meta(cfg, 12000) is None  # missing sidecar -> None
    cfg.reports_dir.mkdir(parents=True)
    meta = {
        "subset": 12000,
        "train_rows": 10800,
        "val_rows": 1200,
        "device": "mps",
        "wall_clock_s": 123.4,
    }
    (cfg.reports_dir / scaled_meta_name(12000)).write_text(json.dumps(meta))
    assert _read_scale_meta(cfg, 12000) == meta


def test_scale_ladder_figure_groups_by_device() -> None:
    rows = [
        {
            "run": "distilbert (bounded CPU rung)",
            "train_rows": 3600,
            "device": "cpu",
            "f1_macro": 0.9021,
        },
        {"run": "distilbert_scale_4000", "train_rows": 3600, "device": "mps", "f1_macro": 0.9010},
        {"run": "distilbert_scale_12000", "train_rows": 10800, "device": "mps", "f1_macro": 0.9270},
        {"run": "distilbert_full_120k", "train_rows": 108000, "device": "mps", "f1_macro": 0.9460},
    ]
    fig = scale_ladder_figure(rows)
    # one trace per device; the mps series connects rungs, cpu is a lone marker
    assert len(fig.data) == 2
    by_name = {t.name: t for t in fig.data}
    assert set(by_name) == {"cpu", "mps"}
    assert len(by_name["cpu"].x) == 1
    assert list(by_name["mps"].x) == [3600, 10800, 108000]
    assert by_name["mps"].mode == "lines+markers"
    assert by_name["cpu"].mode == "markers"
    # log-x axis; the takeaway quantifies the same-rows device twin gap
    assert fig.layout.xaxis.type == "log"
    title = str(fig.layout.title.text)
    assert "Δ 0.0011 F1" in title
    assert "3,600" in title


def test_scale_ladder_figure_without_twin_rungs() -> None:
    rows = [
        {"run": "a", "train_rows": 3600, "device": "cpu", "f1_macro": 0.9},
        {"run": "b", "train_rows": 108000, "device": "mps", "f1_macro": 0.95},
    ]
    fig = scale_ladder_figure(rows)
    assert len(fig.data) == 2
    assert "data size" in str(fig.layout.title.text).lower()


# --- fresh-holdout inclusion of a persisted rung -----------------------------


class _FakeBaseline:
    """Stand-in TF-IDF pipeline: flat-confidence predict/predict_proba."""

    def __init__(self, proba: np.ndarray) -> None:
        self._proba = proba

    def predict(self, texts: list[str]) -> np.ndarray:
        return self._proba.argmax(axis=1)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return self._proba


def test_run_fresh_holdout_scores_persisted_scale_rung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A distilbert_scale_<N>.pt artifact is scored on the fresh holdout too."""
    from nlp_classification import fresh_holdout as fh

    cfg = _cfg(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    (cfg.data_dir / "label_names.json").write_text(json.dumps(NAMES))
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    for name in ("baseline.joblib", "distilbert.pt", "distilbert_tuned.pt", "encoder_b.pt"):
        (cfg.models_dir / name).write_bytes(b"x")
    # one controlled-ladder rung persisted (12000); 4000/40000 never trained
    (cfg.models_dir / scaled_model_name(12000)).write_bytes(b"x")
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "selection.json").write_text(
        json.dumps({"winner": "hpo_retrained", "margin_f1_macro": 0.001})
    )

    n = cfg.fresh_holdout_samples
    rng = np.random.default_rng(0)
    base = rng.dirichlet(np.ones(N_CLASSES), size=n)
    nn_probas = {}
    for i, name in enumerate(("wave2", "hpo", "encoder_b", "scale")):
        shifted = base.copy()
        shifted[:, i % N_CLASSES] += 0.5  # distinct per model so rows differ
        nn_probas[name] = shifted / shifted.sum(axis=1, keepdims=True)

    monkeypatch.setattr(
        fh,
        "load_baseline",
        lambda path: _FakeBaseline(np.full((n, N_CLASSES), 0.25)),
    )
    monkeypatch.setattr(fh, "load_tokenizer", lambda name: object())
    monkeypatch.setattr(fh, "tokenize_dataset", lambda ds, tok, ml: ds)
    monkeypatch.setattr(fh, "build_nn_model", lambda cfg_, n_labels: object())
    monkeypatch.setattr(fh, "load_nn_state_dict", lambda model, path, device: model)
    # scoring order: wave2, hpo, encoder_b, then the persisted scale rung;
    # exhausting the queue proves the rung went through predict_proba_nn
    queue = [nn_probas["wave2"], nn_probas["hpo"], nn_probas["encoder_b"], nn_probas["scale"]]
    monkeypatch.setattr(fh, "predict_proba_nn", lambda model, ds, device, bs: queue.pop(0))
    monkeypatch.setattr(fh, "FULLDATA_MODEL_PATH", "no_such_model.pt")

    def loader() -> DatasetDict:
        return DatasetDict({"test": Dataset.from_dict(_rows(400), features=FEATURES)})

    doc = run_fresh_holdout(cfg, loader=loader)

    assert queue == []  # all four artifacts (incl. the rung) were scored
    assert "distilbert_scale_12000" in doc["runs"]
    assert "distilbert_scale_4000" not in doc["runs"]  # no artifact -> no row
    # the rung row carries the same metric contract as every other run
    assert {"accuracy", "f1_macro", "f1_weighted"} <= set(doc["runs"]["distilbert_scale_12000"])
    # cascade endpoints still reproduce the two constituents
    by_tau = {row["tau"]: row for row in doc["cascade"]["rows"]}
    assert by_tau[0.25]["escalation_rate"] == 0.0
    assert by_tau[1.0]["escalation_rate"] == 1.0
