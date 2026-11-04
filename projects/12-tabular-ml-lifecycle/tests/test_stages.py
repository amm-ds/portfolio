"""Stage smoke tests (synthetic, tmp dirs): prepare → features → report assembly."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from portfolio_core.schemas import DatasetContract
from tabular_ml_lifecycle import figures
from tabular_ml_lifecycle.config import LifecycleConfig
from tabular_ml_lifecycle.data import split_windows
from tabular_ml_lifecycle.report import build_report
from tabular_ml_lifecycle.stages import evaluate_core, features_core, prepare_core, train_core


def test_prepare_core_synthetic(small_cfg: LifecycleConfig) -> None:
    out = prepare_core(small_cfg)
    assert out.exists()
    contract = DatasetContract.model_validate_json(
        (small_cfg.data_dir / "dataset_contract.json").read_text()
    )
    frame = pd.read_parquet(out)
    assert contract.n_rows == len(frame)
    assert (small_cfg.reports_dir / "dq_report.md").exists()
    assert "hourly_grid" in (small_cfg.reports_dir / "dq_report.md").read_text()


def test_features_core_writes_contract(small_cfg: LifecycleConfig) -> None:
    prepare_core(small_cfg)
    contract_path = features_core(small_cfg)
    contract = json.loads(contract_path.read_text())
    windows = split_windows(140 * 24, small_cfg.val_weeks, small_cfg.test_weeks)
    assert contract["split"]["n_test"] == windows.n_test
    assert contract["split"]["n_val"] == windows.n_val
    assert set(contract["selected"]) <= set(contract["candidates"])
    for name in ("train", "val", "test"):
        assert (small_cfg.data_dir / f"features_{name}.parquet").exists()
    assert (small_cfg.data_dir / "series.parquet").exists()
    assert (small_cfg.reports_dir / "figures" / "mi_lollipop.json").exists()


def test_train_and_evaluate_core_smoke(small_cfg: LifecycleConfig) -> None:
    """Small end-to-end: train the ladder, score once, bootstrap excludes zero."""
    prepare_core(small_cfg)
    features_core(small_cfg)
    train_core(small_cfg)
    metrics_path = evaluate_core(small_cfg)
    metrics = json.loads(metrics_path.read_text())
    for name in ("seasonal_naive", "ridge", "random_forest", "lightgbm_hpo", "mlp"):
        assert name in metrics, name
        for key in ("mae", "rmse", "mape"):
            assert metrics[name][key] >= 0
    meta = metrics["_meta"]
    ci = meta["mae_improvement_vs_floor_ci"]
    assert ci["n_boot"] == small_cfg.bootstrap_resamples
    assert ci["point"] > 0  # at least one learned model must beat the floor here
    assert len(meta["ablation"]) == 8
    assert sum(1 for row in meta["ablation"] if row["selected"]) == 1
    metadata = json.loads((small_cfg.reports_dir / "evaluation_metadata.json").read_text())
    for block in ("protocol", "versions", "hardware", "runtime"):
        assert block in metadata
    assert metadata["runtime"]["evaluate_s"] > 0


def test_report_assembly_smoke(small_cfg: LifecycleConfig) -> None:
    """report.html + results.md rebuild offline from committed-shaped artifacts."""
    reports_dir = small_cfg.reports_dir
    fig = figures.residual_vs_fitted_figure(
        np.linspace(0, 100, 50), np.linspace(0, 100, 50) + np.linspace(-5, 5, 50)
    )
    (reports_dir / "figures").mkdir(parents=True, exist_ok=True)
    fig.write_json(str(reports_dir / "figures" / "residual_vs_fitted.json"))
    (reports_dir / "metrics.json").write_text(
        json.dumps(
            {
                "seasonal_naive": {"mae": 90.0, "rmse": 120.0, "mape": 30.0},
                "mlp": {"mae": 60.0, "rmse": 85.0, "mape": 18.0},
                "_meta": {
                    "champion": "mlp",
                    "mae_improvement_vs_floor_ci": {
                        "point": 30.0,
                        "lo": 20.0,
                        "hi": 40.0,
                        "n_boot": 2000,
                        "significant_95": True,
                    },
                    "ablation": [
                        {
                            "dropout_on": True,
                            "weight_decay_on": True,
                            "early_stopping_on": True,
                            "val_mae": 61.0,
                            "test_mae": 60.0,
                            "selected": True,
                        }
                    ],
                },
            }
        )
    )
    (reports_dir / "evaluation_metadata.json").write_text(
        json.dumps(
            {
                "protocol": "smoke protocol",
                "versions": {},
                "hardware": {},
                "runtime": {},
                "limits": ["smoke limit"],
            }
        )
    )
    out = build_report(reports_dir, Path(__file__).resolve().parents[1])
    assert out.exists()
    results = (reports_dir / "results.md").read_text()
    assert "smoke protocol" in results
    assert "tabular MLP (PyTorch)" in results
    assert "smoke limit" in results
