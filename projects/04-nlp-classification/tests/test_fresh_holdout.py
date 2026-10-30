"""Fresh-holdout selection + routing sweep tests (offline, mocked artifacts).

The network-touching pieces (dataset load, tokenizer, persisted encoders) are
injected: the loader comes from ``tiny_loader`` and every model artifact is
monkeypatched, so the tests exercise the draw logic, the metrics plumbing and
the cascade endpoints without weights on disk.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from nlp_classification.config import NLPConfig
from nlp_classification.data import LABEL_COLUMN, TEXT_COLUMN, stratified_subsample_indices
from nlp_classification.fresh_holdout import draw_fresh_holdout, run_fresh_holdout

N_CLASSES = 4
NAMES = ["World", "Sports", "Business", "Sci/Tech"]


def _rows(n: int) -> dict[str, list[str] | list[int]]:
    return {
        TEXT_COLUMN: [f"{NAMES[i % N_CLASSES]} item {i} words here" for i in range(n)],
        LABEL_COLUMN: [i % N_CLASSES for i in range(n)],
    }


def _cfg(tmp_path: Path) -> NLPConfig:
    return NLPConfig(
        test_samples=100,
        fresh_holdout_samples=100,
        cascade_taus=[0.0, 0.25, 0.5, 1.0],  # 0.25 == the fake router's flat confidence
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )


def _local_loader() -> "object":
    """400-row balanced in-memory AG News-like test partition (no network)."""
    from nlp_classification.shims import ClassLabel, Dataset, DatasetDict, Features, Value

    features = Features({TEXT_COLUMN: Value("string"), LABEL_COLUMN: ClassLabel(names=NAMES)})
    return lambda: DatasetDict({"test": Dataset.from_dict(_rows(400), features=features)})


def test_fresh_holdout_disjoint_from_bounded(tmp_path: Path) -> None:
    """The fresh draw must be an exact-complement subsample: zero overlap."""
    cfg = _cfg(tmp_path)
    raw_test = _local_loader()()["test"]
    fresh, provenance = draw_fresh_holdout(cfg, raw_test)

    bounded = set(stratified_subsample_indices(raw_test, cfg.test_samples, seed=cfg.seed + 1))
    # map fresh rows back to source rows by text (labels repeat; texts are unique)
    texts = list(raw_test[TEXT_COLUMN])
    fresh_source_idx = {texts.index(t) for t in fresh[TEXT_COLUMN]}
    assert fresh_source_idx.isdisjoint(bounded)
    assert provenance["overlap_with_bounded"] == 0
    assert provenance["n_fresh"] == len(fresh) == cfg.fresh_holdout_samples
    assert provenance["n_complement"] == len(raw_test) - len(bounded)
    # class balance preserved (stratified draw from a balanced complement)
    counts = [int(np.sum(np.asarray(fresh[LABEL_COLUMN]) == i)) for i in range(N_CLASSES)]
    assert max(counts) - min(counts) <= 1


def test_fresh_holdout_draw_deterministic(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    raw_test = _local_loader()()["test"]
    a, _ = draw_fresh_holdout(cfg, raw_test)
    b, _ = draw_fresh_holdout(cfg, raw_test)
    assert list(a[TEXT_COLUMN]) == list(b[TEXT_COLUMN])


class _FakeBaseline:
    """Stand-in TF-IDF pipeline: predict = argmax of a fixed proba matrix."""

    def __init__(self, proba: np.ndarray) -> None:
        self._proba = proba

    def predict(self, texts: list[str]) -> np.ndarray:
        return self._proba.argmax(axis=1)

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return self._proba


def _fake_nn_probas(n: int) -> dict[str, np.ndarray]:
    """Distinct proba matrices per artifact role (hpo is the most confident)."""
    rng = np.random.default_rng(0)
    base = rng.dirichlet(np.ones(N_CLASSES), size=n)
    out = {}
    for i, name in enumerate(("wave2", "hpo", "encoder_b")):
        shifted = base.copy()
        shifted[:, i % N_CLASSES] += 0.5  # different per model so winners differ
        out[name] = shifted / shifted.sum(axis=1, keepdims=True)
    return out


def _patch_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, n: int) -> None:
    from nlp_classification import fresh_holdout as fh

    cfg = _cfg(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    (cfg.data_dir / "label_names.json").write_text(json.dumps(NAMES))
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    for name in ("baseline.joblib", "distilbert.pt", "distilbert_tuned.pt", "encoder_b.pt"):
        (cfg.models_dir / name).write_bytes(b"x")
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "selection.json").write_text(
        json.dumps({"winner": "hpo_retrained", "margin_f1_macro": 0.001})
    )

    nn_probas = _fake_nn_probas(n)
    monkeypatch.setattr(
        fh,
        "load_baseline",
        lambda path: _FakeBaseline(np.full((n, N_CLASSES), 0.25)),  # flat confidence
    )
    monkeypatch.setattr(fh, "load_tokenizer", lambda name: object())
    monkeypatch.setattr(fh, "tokenize_dataset", lambda ds, tok, ml: ds)
    monkeypatch.setattr(fh, "build_nn_model", lambda cfg_, n_labels: object())
    monkeypatch.setattr(fh, "load_nn_state_dict", lambda model, path, device: model)
    # the loop calls the three artifacts in this order; each exactly once
    queue = [nn_probas["wave2"], nn_probas["hpo"], nn_probas["encoder_b"]]
    monkeypatch.setattr(fh, "predict_proba_nn", lambda model, ds, device, bs: queue.pop(0))
    # no full-data artifact in the mocked project
    monkeypatch.setattr(fh, "FULLDATA_MODEL_PATH", "no_such_model.pt")


def test_run_fresh_holdout_endpoints_and_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _cfg(tmp_path)
    _patch_artifacts(monkeypatch, tmp_path, cfg.fresh_holdout_samples)

    doc = run_fresh_holdout(cfg, loader=_local_loader())

    assert doc["fresh_holdout"]["n_fresh"] == cfg.fresh_holdout_samples
    assert set(doc["runs"]) == {
        "baseline_tfidf_logreg",
        "distilbert_wave2_artifact",
        "distilbert_hpo_retrained",
        "encoder_b",
    }
    for run in doc["runs"].values():
        assert {"accuracy", "f1_macro", "f1_weighted"} <= set(run)

    sel = doc["selection_on_fresh"]
    assert set(sel["candidates_f1_macro"]) == {"wave2_artifact", "hpo_retrained"}
    assert sel["test_selected"] == "hpo_retrained"
    # the hpo fake is the most confident -> wins on the fresh holdout too
    assert sel["fresh_winner"] == "hpo_retrained"
    assert sel["agrees_with_test_selection"]

    cascade = doc["cascade"]["rows"]
    taus = [row["tau"] for row in cascade]
    assert taus == sorted(taus)
    # flat router confidence 0.25: tau<=0.25 escalates nothing (pure TF-IDF),
    # tau>0.25 escalates everything (pure transformer = the served hpo model)
    by_tau = {row["tau"]: row for row in cascade}
    base_f1 = doc["runs"]["baseline_tfidf_logreg"]["f1_macro"]
    hpo_f1 = doc["runs"]["distilbert_hpo_retrained"]["f1_macro"]
    assert by_tau[min(taus)]["escalation_rate"] == 0.0
    assert by_tau[min(taus)]["f1_macro"] == pytest.approx(base_f1)
    assert by_tau[max(taus)]["escalation_rate"] == 1.0
    assert by_tau[max(taus)]["f1_macro"] == pytest.approx(hpo_f1)

    out = tmp_path / "reports" / "fresh_holdout.json"
    assert out.exists()
    on_disk = json.loads(out.read_text())
    assert on_disk["selection_on_fresh"]["fresh_winner"] == "hpo_retrained"
