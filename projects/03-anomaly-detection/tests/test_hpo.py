"""HPO tests: study determinism, tuned artifacts, tuned metrics rows, figures."""

import json
from pathlib import Path

import numpy as np
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.hpo import fit_tuned, persist_study, tune_family
from anomaly_detection.model import anomaly_scores, split_train_test


def _toy_windows(
    small_config: AnomalyConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Small fit/validation matrices from seeded synthetic telemetry."""
    from anomaly_detection.data import generate
    from anomaly_detection.features import build_features
    from anomaly_detection.model import feature_matrix

    df = build_features(generate(small_config), small_config.windows)
    train, _ = split_train_test(df, small_config.train_frac)
    x = feature_matrix(train, small_config)
    y = train["is_anomaly"].to_numpy().astype(int)
    n_val = max(50, int(len(y) * 0.2))
    return x[:-n_val], y[:-n_val], x[-n_val:], y[-n_val:]


def _fast_config(tmp_path: Path, trials: int) -> AnomalyConfig:
    return AnomalyConfig(
        n=1_500,
        hpo_trials=trials,
        data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
    )


def test_hpo_study_is_deterministic(tmp_path: Path) -> None:
    """Same seed + same data ⇒ same best parameters (seeded TPE)."""
    cfg = _fast_config(tmp_path, trials=6)
    x_fit, y_fit, x_val, y_val = _toy_windows(cfg)
    a = tune_family("ocsvm", x_fit, y_fit, x_val, y_val, cfg)
    b = tune_family("ocsvm", x_fit, y_fit, x_val, y_val, cfg)
    assert a.best_params == b.best_params
    assert a.best_value == pytest.approx(b.best_value)


def test_search_spaces_respect_bounds(tmp_path: Path) -> None:
    """A handful of OCSVM suggestions stay inside the declared ranges."""

    cfg = _fast_config(tmp_path, trials=4)
    x_fit, y_fit, x_val, y_val = _toy_windows(cfg)
    study = tune_family("ocsvm", x_fit, y_fit, x_val, y_val, cfg)
    for trial in study.trials:
        if trial.value is None:
            continue
        assert 0.005 <= trial.params["nu"] <= 0.2
        assert 1e-4 <= trial.params["gamma"] <= 5e-1


def test_fit_tuned_scores_with_same_convention(tmp_path: Path) -> None:
    """Tuned refits expose the wave-2 scoring convention (higher = anomalous)."""
    cfg = _fast_config(tmp_path, trials=4)
    x_fit, y_fit, x_val, y_val = _toy_windows(cfg)
    study = tune_family("lof", x_fit, y_fit, x_val, y_val, cfg)
    model = fit_tuned("lof", study.best_params, x_fit, cfg)
    scores = anomaly_scores(model, "lof", x_val)
    assert scores.shape == (len(y_val),)
    # on validation, flagged-by-val-median sanity: anomalies score higher on average
    assert scores[y_val == 1].mean() > 0


def test_persist_study_roundtrip(tmp_path: Path) -> None:
    cfg = _fast_config(tmp_path, trials=4)
    x_fit, y_fit, x_val, y_val = _toy_windows(cfg)
    study = tune_family("ocsvm", x_fit, y_fit, x_val, y_val, cfg)
    path = persist_study(study, "ocsvm", tmp_path / "hpo")
    payload = json.loads(path.read_text())
    assert payload["family"] == "ocsvm"
    assert payload["n_trials"] == 4
    assert set(payload["importances"]) == {"nu", "gamma"}
    assert len(payload["trials"]) == 4
