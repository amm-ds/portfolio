"""Served-model artifact: deterministic re-derivation → native + ONNX → parity gate.

The train stage re-implements experiment 12's committed v2 recipe end to end
(ingest → v2 features → selection → seeded LightGBM HPO + final fit), scores
the frozen test window once, persists the serving artifacts under
``data/models/``, and enforces two hard gates before anything downstream may
run:

- the reproduction gate: derived test MAE must match 12's committed v2
  LightGBM MAE within ``reproduction_tolerance`` (same data, seed, recipe);
- the parity gate: ONNX Runtime predictions must match native LightGBM
  predictions on a fixed seeded probe grid within ``parity_tolerance``
  (max-abs, plus the float32 relative term in ``check_parity``).

The v2 MLP (12's validation runner-up) is cited as the comparison from 12's
committed metrics — it is not re-trained here. The v1 MLP run this study
served before the v2 promotion is kept under ``previous_runs.v1``.
"""

import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.logging import get_logger

from model_serving.config import ServingConfig
from model_serving.data import (
    TARGET_COL,
    frame_sha256,
    load_uci_frame,
    make_synthetic_frame,
    split_windows,
)
from model_serving.features import (
    apply_nan_lag_policy,
    apply_split,
    build_features,
    select_features,
)
from model_serving.lgbm import run_hpo, train_lgbm_final

log = get_logger(__name__)

MODELS_DIRNAME = "models"
ONNX_FILENAME = "model.onnx"
NATIVE_FILENAME = "lightgbm.pkl"
META_FILENAME = "lgbm_meta.json"


class ParityError(RuntimeError):
    """ONNX predictions deviate from native predictions beyond the gate."""


class ReproductionError(RuntimeError):
    """The re-derived served model does not reproduce experiment 12's committed MAE."""


@dataclass
class ChampionArtifact:
    """Paths + summary of everything the train stage persists."""

    models_dir: Path
    metrics: dict[str, Any]

    def path(self, name: str) -> Path:
        return self.models_dir / name


def export_onnx(model: Any, n_features: int, path: Path, opset: int) -> Path:
    """Export the fitted LightGBM to ONNX (TreeEnsembleRegressor) via onnxmltools.

    onnxmltools' converter supports up to opset 15; onnxruntime runs the graph
    on CPU. The graph is float32 — the parity gate prices that against the
    native float64 predictor on the seeded probe grid.
    """
    from onnxmltools.convert import convert_lightgbm  # type: ignore[import-untyped]  # no stubs
    from onnxmltools.convert.common.data_types import (  # type: ignore[import-untyped]  # no stubs
        FloatTensorType,
    )

    onnx_model = convert_lightgbm(
        model,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=opset,
    )
    path.write_bytes(onnx_model.SerializeToString())
    return path


def probe_grid(n: int, seed: int, numeric_cols: list[str]) -> pd.DataFrame:
    """Fixed seeded probe grid over the contract's valid ranges (DQ bounds).

    The same grid drives the train-stage parity gate and the benchmark's
    request payloads, so both are reproducible from the seed alone. Ranges
    follow 12's DQ gates; lags span the observed count range.
    """
    rng = np.random.default_rng(seed)
    columns: dict[str, np.ndarray] = {}
    for col in numeric_cols:
        if col in ("temp", "atemp"):
            columns[col] = rng.uniform(0.0, 1.0, n)
        elif col == "hum":
            columns[col] = rng.uniform(0.05, 0.98, n)
        elif col == "windspeed":
            columns[col] = rng.uniform(0.0, 0.85, n)
        elif col == "weathersit":
            columns[col] = rng.integers(1, 5, n).astype(float)
        elif col in ("holiday", "workingday"):
            columns[col] = rng.integers(0, 2, n).astype(float)
        elif col.endswith(("_sin", "_cos")):
            columns[col] = rng.uniform(-1.0, 1.0, n)
        elif col.startswith("cnt_lag_"):
            columns[col] = rng.uniform(0.0, 800.0, n)
        else:  # pragma: no cover - the contract has no other columns
            raise ValueError(f"probe grid has no range for column {col!r}")
    # Column order is part of the contract.
    return pd.DataFrame(columns)[numeric_cols]


def raw_onnx_predict(models_dir: Path, grid: pd.DataFrame, numeric_cols: list[str]) -> np.ndarray:
    """Raw ONNX output (rentals) for the probe grid — what the service's ONNX
    backend computes."""
    import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime ships no stubs

    session = ort.InferenceSession(
        str(models_dir / ONNX_FILENAME), providers=["CPUExecutionProvider"]
    )
    x = grid[numeric_cols].to_numpy(dtype=np.float32)
    (out,) = session.run(None, {"input": x})
    return np.asarray(out, dtype=float).ravel()


def check_parity(
    native: np.ndarray, onnx: np.ndarray, tolerance: float, rel: float = 1e-5
) -> float:
    """Hard gate: max-abs deviation of the raw prediction (rentals).

    Absolute ``tolerance`` plus a float32 relative term (eps x scale): the
    exported tree ensemble accumulates leaf values in float32, so kernel-order
    noise (~1e-7 x |output|) cannot fail the gate on an ill-scaled model,
    while a genuinely wrong graph is caught by the absolute term. Same gate
    shape as the v1 MLP study.
    """
    max_abs = float(np.max(np.abs(native - onnx)))
    limit = tolerance + rel * max(1.0, float(np.max(np.abs(native))))
    if max_abs > limit:
        raise ParityError(
            f"ONNX/native parity gate failed: max-abs {max_abs:.6g} > limit {limit:.6g}"
        )
    return max_abs


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _mae_rmse(y_true: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = pred - y_true
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
    }


def _example_row(test_df: pd.DataFrame, selected: list[str]) -> dict[str, float]:
    """One real, typical test-window row (nearest to the column medians).

    Rounded, label-free — the worked example in the README and report. It is a
    genuine observation, so it provably passes the service's request schema.
    """
    medians = test_df[selected].median()
    distances = ((test_df[selected] - medians).abs() / (test_df[selected].std() + 1e-9)).sum(axis=1)
    row = test_df.loc[int(distances.idxmin())]
    example: dict[str, float] = {}
    for col in selected:
        example[col] = round(float(row[col]), 4)
    return example


def train_core(cfg: ServingConfig) -> ChampionArtifact:
    """Re-derive the served model, persist artifacts, enforce both hard gates."""
    started = time.perf_counter()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    if cfg.data_source == "uci":
        df = load_uci_frame(cfg.uci_source, cfg.uci_sha256)
        source_name = "uci_bike_sharing_hourly"
    else:
        df = make_synthetic_frame(cfg.seed, 728)
        source_name = "synthetic_twin"
    dataset_sha = frame_sha256(df)
    log.info("train: loaded %s frame (%d rows, sha256 %s…)", source_name, len(df), dataset_sha[:12])

    windows = split_windows(len(df), cfg.val_weeks, cfg.test_weeks)
    win_dict: dict[str, Any] = {
        "scheme": "time-based",
        "val_weeks": cfg.val_weeks,
        "test_weeks": cfg.test_weeks,
        "n_train": windows.n_train - cfg.max_lag,
        "n_val": windows.n_val,
        "n_test": windows.n_test,
    }
    featured = build_features(df, cfg.lag_hours, cfg.lag_mode)
    train_df, val_df, test_df = apply_split(featured, windows, cfg.max_lag)
    train_df, val_df, test_df, nan_counts = apply_nan_lag_policy(
        train_df, val_df, test_df, cfg.lag_hours, cfg.lag_mode
    )

    selection = select_features(cfg, train_df, val_df)
    selected = selection.selected
    X_train, y_train = train_df[selected], train_df[TARGET_COL].astype(float)
    X_val, y_val = val_df[selected], val_df[TARGET_COL].astype(float)

    hpo = run_hpo(cfg, X_train, y_train, X_val, y_val)
    model = train_lgbm_final(cfg, X_train, y_train, X_val, y_val, hpo.best_params)

    val_pred = np.asarray(model.predict(val_df[selected]), dtype=float)
    test_pred = np.asarray(model.predict(test_df[selected]), dtype=float)
    val_metrics = _mae_rmse(val_df[TARGET_COL].to_numpy(dtype=float), val_pred)
    test_metrics = _mae_rmse(test_df[TARGET_COL].to_numpy(dtype=float), test_pred)

    # Gate 1 — reproduction of experiment 12's committed v2 score.
    abs_diff = abs(test_metrics["mae"] - cfg.champion_expected_test_mae)
    reproduction = {
        "expected_test_mae": cfg.champion_expected_test_mae,
        "derived_test_mae": test_metrics["mae"],
        "abs_diff": abs_diff,
        "tolerance": cfg.reproduction_tolerance,
        "passed": abs_diff <= cfg.reproduction_tolerance,
    }
    if not reproduction["passed"]:
        raise ReproductionError(
            f"served-model reproduction failed: derived {test_metrics['mae']:.4f} vs expected "
            f"{cfg.champion_expected_test_mae:.4f} (tolerance {cfg.reproduction_tolerance})"
        )

    models_dir = cfg.data_dir / MODELS_DIRNAME
    models_dir.mkdir(parents=True, exist_ok=True)
    with (models_dir / NATIVE_FILENAME).open("wb") as fh:
        pickle.dump(model, fh)
    best_iteration = int(getattr(model, "best_iteration_", 0) or 0)
    _write_json(
        models_dir / META_FILENAME,
        {
            "family": "lightgbm",
            "numeric_cols": selected,
            "best_iteration": best_iteration,
            "n_estimators_cap": cfg.lgbm.n_estimators,
            "hpo_best_params": hpo.best_params,
        },
    )
    contract = selection.to_contract(cfg, win_dict)
    contract["dataset"] = {"source": source_name, "frame_sha256": dataset_sha}
    contract["nan_lag_policy"] = {
        **nan_counts,
        "rule": (
            "NaN-lag rows are dropped from train/validation (complete-case); "
            "the frozen test window keeps every row, its NaN lag cells "
            "median-imputed from the training window."
        ),
    }
    _write_json(models_dir / "feature_contract.json", contract)

    export_onnx(model, len(selected), models_dir / ONNX_FILENAME, cfg.onnx_opset)

    # Gate 2 — ONNX vs native parity on the fixed probe grid (raw prediction,
    # rentals; the graph is float32, the native predictor float64).
    grid = probe_grid(cfg.probe_grid_n, cfg.seed, selected)
    native_pred = np.asarray(model.predict(grid[selected]), dtype=float)
    onnx_pred = raw_onnx_predict(models_dir, grid, selected)
    max_abs = check_parity(native_pred, onnx_pred, cfg.parity_tolerance)
    parity_limit = cfg.parity_tolerance + 1e-5 * max(1.0, float(np.max(np.abs(native_pred))))

    example = _example_row(test_df, selected)
    metrics: dict[str, Any] = {
        "champion": {
            "family": "lightgbm",
            "rederived_from": "projects/12-tabular-ml-lifecycle committed v2 recipe",
            "val_mae": val_metrics["mae"],
            "val_rmse": val_metrics["rmse"],
            "test_mae": test_metrics["mae"],
            "test_rmse": test_metrics["rmse"],
            "best_iteration": best_iteration,
            "hpo_best_params": hpo.best_params,
            "hpo_n_trials": hpo.n_trials,
        },
        "comparison": {
            "v2_mlp_test_mae": cfg.comparison_mlp_test_mae,
            "note": (
                "12's v2 MLP is the validation runner-up (31.94 vs 35.13 on "
                "validation); it is cited from 12's committed metrics, not "
                "re-trained here. The MLP remains a candidate in 12, not the "
                "served model."
            ),
        },
        "reproduction": reproduction,
        "parity": {
            "tolerance": cfg.parity_tolerance,
            "rel_term": 1e-5,
            "limit": parity_limit,
            "space": "raw prediction (rentals); the ONNX graph is float32",
            "max_abs_rentals": max_abs,
            "n_probe": cfg.probe_grid_n,
            "opset": cfg.onnx_opset,
            "passed": True,
        },
        "selection": {
            "selected": selected,
            "pruned_pairs": selection.pruned_pairs,
            "corr_threshold": cfg.corr_threshold,
        },
        "dataset": {"source": source_name, "frame_sha256": dataset_sha, "n_rows": len(df)},
        "example_row": example,
        "train_runtime_s": round(time.perf_counter() - started, 3),
    }
    _write_json(cfg.reports_dir / "train_run.json", metrics)
    log.info(
        "train: test MAE %.4f (reproduction |Δ|=%.6g) | parity max-abs %.3g (limit %.3g) | %.1fs",
        test_metrics["mae"],
        abs_diff,
        max_abs,
        parity_limit,
        metrics["train_runtime_s"],
    )
    return ChampionArtifact(models_dir=models_dir, metrics=metrics)
