"""Champion artifact: deterministic re-derivation → native + ONNX → parity gate.

The train stage re-implements experiment 12's champion path end to end
(ingest → features → selection → hand-written MLP loop), scores the frozen
test window once, persists the serving artifacts under ``data/models/``, and
enforces two hard gates before anything downstream may run:

- the reproduction gate: derived test MAE must match 12's committed champion
  MAE within ``reproduction_tolerance`` (same data, seed, architecture);
- the parity gate: ONNX Runtime predictions must match native torch
  predictions on a fixed seeded probe grid within ``parity_tolerance`` (max-abs).
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from portfolio_core.logging import get_logger

from model_serving.config import ServingConfig
from model_serving.data import (
    TARGET_COL,
    frame_sha256,
    load_uci_frame,
    make_synthetic_frame,
    split_windows,
)
from model_serving.features import apply_split, build_features, select_features
from model_serving.mlp import MLPRegressor, RentalMLP

log = get_logger(__name__)

MODELS_DIRNAME = "models"
ONNX_FILENAME = "model.onnx"


class ParityError(RuntimeError):
    """ONNX predictions deviate from native predictions beyond the gate."""


class ReproductionError(RuntimeError):
    """The re-derived champion does not reproduce experiment 12's committed MAE."""


@dataclass
class ChampionArtifact:
    """Paths + summary of everything the train stage persists."""

    models_dir: Path
    metrics: dict[str, Any]

    def path(self, name: str) -> Path:
        return self.models_dir / name


def export_onnx(model: RentalMLP, n_numeric: int, path: Path, opset: int) -> Path:
    """Export the eval-mode MLP to ONNX with a dynamic batch dimension.

    shortcut: the legacy TorchScript exporter (dynamo=False) — the dynamo
    default needs onnxscript, an extra dep, for a plain embedding+MLP graph;
    upgrade if torch drops the legacy path.
    """
    model.eval()
    hour = torch.arange(4, dtype=torch.long)
    x_num = torch.zeros(4, n_numeric, dtype=torch.float32)
    torch.onnx.export(
        model,
        (hour, x_num),
        str(path),
        opset_version=opset,
        dynamo=False,
        input_names=["hour", "x_num"],
        output_names=["prediction"],
        dynamic_axes={"hour": {0: "batch"}, "x_num": {0: "batch"}, "prediction": {0: "batch"}},
    )
    return path


def probe_grid(n: int, seed: int, numeric_cols: list[str]) -> pd.DataFrame:
    """Fixed seeded probe grid over the contract's valid ranges (DQ bounds).

    The same grid drives the train-stage parity gate and the benchmark's
    request payloads, so both are reproducible from the seed alone.
    """
    rng = np.random.default_rng(seed)
    grid = pd.DataFrame(
        {
            "hour": rng.integers(0, 24, n),
            "temp": rng.uniform(0.0, 1.0, n),
            "hum": rng.uniform(0.05, 0.98, n),
            "windspeed": rng.uniform(0.0, 0.85, n),
            "weathersit": rng.integers(1, 5, n).astype(float),
            "hour_sin": rng.uniform(-1.0, 1.0, n),
            "hour_cos": rng.uniform(-1.0, 1.0, n),
            "weekday_sin": rng.uniform(-1.0, 1.0, n),
            "weekday_cos": rng.uniform(-1.0, 1.0, n),
            "month_sin": rng.uniform(-1.0, 1.0, n),
            "month_cos": rng.uniform(-1.0, 1.0, n),
            "holiday": rng.integers(0, 2, n).astype(float),
            "workingday": rng.integers(0, 2, n).astype(float),
            "cnt_lag_1h": rng.uniform(0.0, 800.0, n),
            "cnt_lag_24h": rng.uniform(0.0, 800.0, n),
            "cnt_lag_168h": rng.uniform(0.0, 800.0, n),
        }
    )
    # Column order is part of the contract: hour first, then the numeric list.
    return grid[["hour", *numeric_cols]]


def raw_onnx_predict(models_dir: Path, grid: pd.DataFrame, numeric_cols: list[str]) -> np.ndarray:
    """Raw ONNX network output (standardized-y space) with the train-fitted
    input standardization applied — exactly what the service backend does."""
    import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime ships no stubs

    session = ort.InferenceSession(
        str(models_dir / ONNX_FILENAME), providers=["CPUExecutionProvider"]
    )
    meta = json.loads((models_dir / "mlp_meta.json").read_text())
    x_mean = np.asarray(meta["x_mean"], dtype=np.float64)
    x_std = np.asarray(meta["x_std"], dtype=np.float64)
    hour = grid["hour"].to_numpy(dtype=np.int64)
    x_num = ((grid[numeric_cols].to_numpy(dtype=np.float64) - x_mean) / x_std).astype(np.float32)
    (out,) = session.run(None, {"hour": hour, "x_num": x_num})
    return np.asarray(out, dtype=float)


def check_parity(
    native_scaled: np.ndarray, onnx_scaled: np.ndarray, tolerance: float, rel: float = 1e-5
) -> float:
    """Hard gate: max-abs deviation of the raw network output (standardized-y
    space). Absolute ``tolerance`` plus a float32 relative term (eps x scale):
    a well-conditioned champion (outputs O(1)) is gated tight by the absolute
    term, while float32 kernel-order noise (~1e-7 x |output|) cannot fail the
    gate on an ill-scaled model. End-to-end deviations scale by y_std exactly.
    """
    max_abs = float(np.max(np.abs(native_scaled - onnx_scaled)))
    limit = tolerance + rel * max(1.0, float(np.max(np.abs(native_scaled))))
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
    for col in ["hour", *selected]:
        example[col] = round(float(row[col]), 4)
    return example


def train_core(cfg: ServingConfig) -> ChampionArtifact:
    """Re-derive the champion, persist artifacts, enforce both hard gates."""
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
    featured = build_features(df, cfg.lag_hours)
    train_df, val_df, test_df = apply_split(featured, windows, cfg.max_lag)

    selection = select_features(cfg, train_df, val_df)
    selected = selection.selected
    mlp_cols = ["hour", *selected]  # raw hour feeds the embedding; never a candidate feature

    reg = MLPRegressor(cfg.mlp, cfg.seed)
    reg.fit(
        train_df[mlp_cols],
        train_df[TARGET_COL].astype(float),
        val_df[mlp_cols],
        val_df[TARGET_COL].astype(float),
        selected,
    )
    if reg.model is None or reg.x_mean is None or reg.x_std is None:
        raise RuntimeError("MLPRegressor fit left no fitted state — this is a pipeline bug")

    val_pred = reg.predict(val_df[mlp_cols])
    test_pred = reg.predict(test_df[mlp_cols])
    val_metrics = _mae_rmse(val_df[TARGET_COL].to_numpy(dtype=float), val_pred)
    test_metrics = _mae_rmse(test_df[TARGET_COL].to_numpy(dtype=float), test_pred)

    # Gate 1 — reproduction of experiment 12's committed champion score.
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
            f"champion reproduction failed: derived {test_metrics['mae']:.4f} vs expected "
            f"{cfg.champion_expected_test_mae:.4f} (tolerance {cfg.reproduction_tolerance})"
        )

    models_dir = cfg.data_dir / MODELS_DIRNAME
    models_dir.mkdir(parents=True, exist_ok=True)
    torch.save(reg.model.state_dict(), models_dir / "mlp.pt")
    arch = {
        "hour_cardinality": 24,
        "n_numeric": len(selected),
        "embed_dim": cfg.mlp.embed_dim,
        "hidden_dims": list(cfg.mlp.hidden_dims),
        "dropout": cfg.mlp.dropout,
        "onnx_inputs": ["hour (int64 [batch])", "x_num (float32 [batch, n_numeric])"],
        "onnx_output": "prediction (float32 [batch]) — standardized y; invert with y_std/y_mean",
    }
    _write_json(models_dir / "mlp_arch.json", arch)
    _write_json(
        models_dir / "mlp_meta.json",
        {
            "numeric_cols": selected,
            "x_mean": reg.x_mean.tolist(),
            "x_std": reg.x_std.tolist(),
            "y_mean": reg.y_mean,
            "y_std": reg.y_std,
            "best_epoch": reg.history.best_epoch,
            "epochs_run": reg.history.epochs_run,
        },
    )
    contract = selection.to_contract(cfg, win_dict)
    contract["dataset"] = {"source": source_name, "frame_sha256": dataset_sha}
    _write_json(models_dir / "feature_contract.json", contract)

    export_onnx(reg.model, len(selected), models_dir / ONNX_FILENAME, cfg.onnx_opset)

    # Gate 2 — ONNX vs native parity on the fixed probe grid (raw network
    # output, standardized-y space; end-to-end deviation = x y_std exactly).
    grid = probe_grid(cfg.probe_grid_n, cfg.seed, selected)
    native_scaled = reg.predict_scaled(grid)
    onnx_scaled = raw_onnx_predict(models_dir, grid, selected)
    max_abs = check_parity(native_scaled, onnx_scaled, cfg.parity_tolerance)

    example = _example_row(test_df, selected)
    metrics: dict[str, Any] = {
        "champion": {
            "family": "tabular_mlp_pytorch",
            "rederived_from": "projects/12-tabular-ml-lifecycle committed recipe",
            "val_mae": val_metrics["mae"],
            "val_rmse": val_metrics["rmse"],
            "test_mae": test_metrics["mae"],
            "test_rmse": test_metrics["rmse"],
            "best_epoch": reg.history.best_epoch,
            "epochs_run": reg.history.epochs_run,
            "train_loss": reg.history.train_loss,
            "val_loss": reg.history.val_loss,
        },
        "reproduction": reproduction,
        "parity": {
            "tolerance": cfg.parity_tolerance,
            "space": "standardized network output (end-to-end deviation = value x y_std)",
            "max_abs_scaled": max_abs,
            "max_abs_rentals": max_abs * reg.y_std,
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
        "train: test MAE %.4f (reproduction |Δ|=%.6g) | parity max-abs %.3g | %.1fs",
        test_metrics["mae"],
        abs_diff,
        max_abs,
        metrics["train_runtime_s"],
    )
    return ChampionArtifact(models_dir=models_dir, metrics=metrics)
