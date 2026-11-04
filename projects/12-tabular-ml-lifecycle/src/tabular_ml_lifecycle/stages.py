"""Stage orchestration: prepare → eda → features → train → evaluate → report.

Each ``*_core`` is a thin, testable function the CLI commands wrap; ``all``
chains them in-process so the full pipeline runs in one interpreter. Only the
evaluate stage touches the test window, and only to write each candidate's
score once.
"""

import json
import os
import pickle
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json

import tabular_ml_lifecycle
from tabular_ml_lifecycle import figures
from tabular_ml_lifecycle.config import LifecycleConfig
from tabular_ml_lifecycle.data import (
    TARGET_COL,
    TIMESTAMP_COL,
    dataset_contract_for,
    load_uci_frame,
    make_synthetic_frame,
    run_dq_gates,
    split_windows,
)
from tabular_ml_lifecycle.features import (
    apply_split,
    build_features,
    mi_lollipop_figure,
    seasonal_naive_predict,
    select_features,
)
from tabular_ml_lifecycle.metrics import (
    mae,
    mape,
    paired_bootstrap_deltas,
    rmse,
)
from tabular_ml_lifecycle.mlp import MLPRegressor, RentalMLP
from tabular_ml_lifecycle.models import (
    learning_curve_points,
    rf_estimator,
    ridge_estimator,
    run_hpo,
    train_lgbm_final,
)

log = get_logger(__name__)

CANDIDATE_MODELS = ["ridge", "random_forest", "lightgbm_hpo", "mlp"]
TEST_LIMITS = [
    "The test window is scored once per candidate; model selection, early "
    "stopping and the ablation choice used validation only.",
    "MAPE denominators are floored at 1 rental; near-zero hours inflate MAPE "
    "even when the absolute error is small — read MAE first.",
    "Two seasons, one city, one system: transfer to other fleets or regimes "
    "is plausible, not measured.",
]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def prepare_core(cfg: LifecycleConfig) -> Path:
    """Fetch the pinned UCI zip (or generate the synthetic twin), gate, persist."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    if cfg.data_source == "uci":
        df = load_uci_frame(cfg.uci_source, cfg.uci_sha256)
        source = cfg.uci_source
        name = "bike_sharing_hourly_uci"
        license_ = "CC BY 4.0 (Fanaee-T & Gama 2013, UCI ML Repository #275)"
        log.info("prepare: loaded UCI bike sharing hour.csv (%d rows)", len(df))
    else:
        df = make_synthetic_frame(cfg.seed, cfg.n_days_synthetic)
        source = "synthetic://tabular_ml_lifecycle.data.make_synthetic_frame"
        name = "bike_sharing_hourly_synthetic"
        license_ = "MIT"
        log.info("prepare: generated synthetic twin (%d rows)", len(df))

    report = run_dq_gates(df)
    (cfg.reports_dir / "dq_report.md").write_text(report.to_markdown() + "\n")
    contract = dataset_contract_for(df, name, source, license_)
    (cfg.data_dir / "dataset_contract.json").write_text(contract.model_dump_json(indent=2) + "\n")

    out = cfg.data_dir / "hour.parquet"
    df.to_parquet(out, index=False)
    log.info(
        "prepare: %d rows, %d/%d DQ checks passed -> %s",
        len(df),
        len(report.checks) - report.n_failed,
        len(report.checks),
        out,
    )
    return out


def eda_core(cfg: LifecycleConfig) -> list[Path]:
    """Three committed EDA figures (line matrix, scatter, correlation heatmap)."""
    df = pd.read_parquet(cfg.data_dir / "hour.parquet")
    figs = {
        "rentals_by_hour_season": figures.rentals_by_hour_season_figure(df),
        "temp_vs_rentals": figures.temp_vs_rentals_figure(df),
        "correlation_heatmap": figures.correlation_heatmap_figure(df),
    }
    paths = []
    for name, fig in figs.items():
        save_html(fig, cfg.reports_dir / "figures" / f"{name}.html")
        paths.append(save_json(fig, cfg.reports_dir / "figures" / f"{name}.json"))
    log.info("eda: %d figures -> reports/figures/", len(figs))
    return paths


def features_core(cfg: LifecycleConfig) -> Path:
    """Build the feature frame, cut the time windows, run selection, write contract."""
    df = pd.read_parquet(cfg.data_dir / "hour.parquet")
    windows = split_windows(len(df), cfg.val_weeks, cfg.test_weeks)
    featured = build_features(df, cfg.lag_hours)
    train, val, test = apply_split(featured, windows, cfg.max_lag)

    keep_cols = list(featured.columns)
    for name, part in (("train", train), ("val", val), ("test", test)):
        part[keep_cols].to_parquet(cfg.data_dir / f"features_{name}.parquet", index=False)

    series = df[[TIMESTAMP_COL, TARGET_COL]].copy()
    series["split"] = "train"
    series.iloc[windows.val, series.columns.get_loc("split")] = "val"
    series.iloc[windows.test, series.columns.get_loc("split")] = "test"
    series.to_parquet(cfg.data_dir / "series.parquet", index=False)

    selection = select_features(cfg, train, val, windows)
    contract_path = cfg.data_dir / "feature_selection.json"
    _write_json(contract_path, selection.to_contract(cfg))

    fig = mi_lollipop_figure(selection)
    save_html(fig, cfg.reports_dir / "figures" / "mi_lollipop.html")
    save_json(fig, cfg.reports_dir / "figures" / "mi_lollipop.json")
    log.info(
        "features: train %d / val %d / test %d rows; %d/%d candidates selected; pruned %s",
        windows.n_train - cfg.max_lag,
        windows.n_val,
        windows.n_test,
        len(selection.selected),
        len(selection.candidates),
        selection.pruned_pairs,
    )
    return contract_path


def _load_split(cfg: LifecycleConfig, name: str) -> pd.DataFrame:
    return pd.read_parquet(cfg.data_dir / f"features_{name}.parquet")


def train_core(cfg: LifecycleConfig) -> Path:
    """Fit the ladder on train, tune on validation, persist every artifact."""
    started = time.perf_counter()
    selection = json.loads((cfg.data_dir / "feature_selection.json").read_text())
    selected: list[str] = selection["selected"]
    train_df, val_df = _load_split(cfg, "train"), _load_split(cfg, "val")
    test_df = _load_split(cfg, "test")  # used ONLY by the ablation record, never for selection
    X_train, y_train = train_df[selected], train_df[TARGET_COL].astype(float)
    X_val, y_val = val_df[selected], val_df[TARGET_COL].astype(float)
    y_test = test_df[TARGET_COL].astype(float)

    series = pd.read_parquet(cfg.data_dir / "series.parquet")
    cnt = pd.Series(series[TARGET_COL].to_numpy(), index=series[TIMESTAMP_COL])
    models_dir = cfg.data_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    def _val_metrics(model: Any, X: pd.DataFrame) -> dict[str, float]:
        pred = model.predict(X)
        y = y_val.to_numpy()
        return {"mae": mae(y, pred), "rmse": rmse(y, pred), "mape": mape(y, pred)}

    val_runs: dict[str, dict[str, float]] = {}
    naive_val = seasonal_naive_predict(cnt, val_df[TIMESTAMP_COL])
    val_runs["seasonal_naive"] = {
        "mae": mae(y_val.to_numpy(), naive_val),
        "rmse": rmse(y_val.to_numpy(), naive_val),
        "mape": mape(y_val.to_numpy(), naive_val),
    }

    ridge = ridge_estimator(cfg, selected).fit(X_train, y_train)
    with (models_dir / "ridge.pkl").open("wb") as fh:
        pickle.dump(ridge, fh)
    val_runs["ridge"] = _val_metrics(ridge, X_val)

    rf = rf_estimator(cfg, cfg.seed, selected).fit(X_train, y_train)
    with (models_dir / "random_forest.pkl").open("wb") as fh:
        pickle.dump(rf, fh)
    val_runs["random_forest"] = _val_metrics(rf, X_val)

    hpo = run_hpo(cfg, X_train, y_train, X_val, y_val)
    lgbm = train_lgbm_final(cfg, X_train, y_train, X_val, y_val, hpo.best_params)
    with (models_dir / "lightgbm.pkl").open("wb") as fh:
        pickle.dump(lgbm, fh)
    val_runs["lightgbm_hpo"] = _val_metrics(lgbm, X_val)

    mlp = MLPRegressor(cfg, cfg.seed)
    mlp_cols = ["hour", *selected]  # raw hour feeds the embedding; never a candidate feature
    X_train_mlp, X_val_mlp = train_df[mlp_cols], val_df[mlp_cols]
    X_test_mlp = test_df[mlp_cols]
    mlp.fit(X_train_mlp, y_train, X_val_mlp, y_val, selected)
    torch.save(mlp.model.state_dict(), models_dir / "mlp.pt")  # type: ignore[union-attr]
    _write_json(
        models_dir / "mlp_meta.json",
        {
            "numeric_cols": selected,
            "x_mean": mlp.x_mean.tolist() if mlp.x_mean is not None else [],
            "x_std": mlp.x_std.tolist() if mlp.x_std is not None else [],
            "y_mean": mlp.y_mean,
            "y_std": mlp.y_std,
            "best_epoch": mlp.history.best_epoch,
            "epochs_run": mlp.history.epochs_run,
        },
    )
    val_runs["mlp"] = _val_metrics(mlp, X_val_mlp)

    # Overfitting-control artifacts: per-epoch losses, learning curves, ablation.
    loss_fig = figures.mlp_loss_curves_figure(
        mlp.history.train_loss, mlp.history.val_loss, mlp.history.best_epoch
    )
    save_html(loss_fig, cfg.reports_dir / "figures" / "mlp_loss_curves.html")
    save_json(loss_fig, cfg.reports_dir / "figures" / "mlp_loss_curves.json")

    lgbm_points = learning_curve_points(
        cfg,
        lambda Xs, ys: train_lgbm_final(cfg, Xs, ys, X_val, y_val, hpo.best_params),
        X_train,
        y_train,
        X_val,
        y_val,
        cfg.seed,
    )
    mlp_points = learning_curve_points(
        cfg,
        lambda Xs, ys: MLPRegressor(cfg, cfg.seed + 1).fit(Xs, ys, X_val_mlp, y_val, selected),
        X_train_mlp,
        y_train,
        X_val_mlp,
        y_val,
        cfg.seed + 1,
    )
    lc_fig = figures.learning_curves_figure({"lightgbm_hpo": lgbm_points, "mlp": mlp_points})
    save_html(lc_fig, cfg.reports_dir / "figures" / "learning_curves.html")
    save_json(lc_fig, cfg.reports_dir / "figures" / "learning_curves.json")

    ablation_rows = mlp.ablation(
        X_train_mlp, y_train, X_val_mlp, y_val, X_test_mlp, y_test, selected
    )
    ablation_payload = [
        {
            "variant": r.variant,
            "dropout_on": r.dropout_on,
            "weight_decay_on": r.weight_decay_on,
            "early_stopping_on": r.early_stopping_on,
            "val_mae": r.val_mae,
            "test_mae": r.test_mae,
            "epochs_run": r.epochs_run,
            "selected": r.dropout_on and r.weight_decay_on and r.early_stopping_on,
        }
        for r in ablation_rows
    ]
    abl_fig = figures.ablation_dotplot_figure(ablation_payload)
    save_html(abl_fig, cfg.reports_dir / "figures" / "ablation_dotplot.html")
    save_json(abl_fig, cfg.reports_dir / "figures" / "ablation_dotplot.json")

    train_runs: dict[str, Any] = {
        "val": val_runs,
        "hpo": {
            "best_params": hpo.best_params,
            "n_trials": hpo.n_trials,
            "best_val_mae": hpo.best_val_mae,
            "time_budget_s": hpo.time_budget_s,
            "trial_cap": hpo.trial_cap,
        },
        "mlp": {
            "train_loss": mlp.history.train_loss,
            "val_loss": mlp.history.val_loss,
            "best_epoch": mlp.history.best_epoch,
            "epochs_run": mlp.history.epochs_run,
        },
        "learning_curves": {
            "lightgbm_hpo": {str(k): v for k, v in lgbm_points.items()},
            "mlp": {str(k): v for k, v in mlp_points.items()},
        },
        "ablation": ablation_payload,
        "selected_features": selected,
        "train_runtime_s": round(time.perf_counter() - started, 3),
    }
    out = cfg.reports_dir / "train_runs.json"
    _write_json(out, train_runs)
    log.info(
        "train: val MAE naive=%.1f ridge=%.1f rf=%.1f lgbm=%.1f mlp=%.1f | %d HPO trials | %.1fs",
        val_runs["seasonal_naive"]["mae"],
        val_runs["ridge"]["mae"],
        val_runs["random_forest"]["mae"],
        val_runs["lightgbm_hpo"]["mae"],
        val_runs["mlp"]["mae"],
        hpo.n_trials,
        train_runs["train_runtime_s"],
    )
    return out


def evaluate_core(cfg: LifecycleConfig) -> Path:
    """Score every candidate once on the frozen test window; bootstrap the gap."""
    started = time.perf_counter()
    train_runs = json.loads((cfg.reports_dir / "train_runs.json").read_text())
    test_df = _load_split(cfg, "test")
    selected = train_runs["selected_features"]
    X_test, y_test = test_df[selected], test_df[TARGET_COL].astype(float).to_numpy()

    series = pd.read_parquet(cfg.data_dir / "series.parquet")
    cnt = pd.Series(series[TARGET_COL].to_numpy(), index=series[TIMESTAMP_COL])
    models_dir = cfg.data_dir / "models"

    preds: dict[str, np.ndarray] = {
        "seasonal_naive": seasonal_naive_predict(cnt, test_df[TIMESTAMP_COL])
    }
    for name, artifact in (
        ("ridge", "ridge.pkl"),
        ("random_forest", "random_forest.pkl"),
        ("lightgbm_hpo", "lightgbm.pkl"),
    ):
        with (models_dir / artifact).open("rb") as fh:
            model = pickle.load(fh)  # noqa: S301 - pipeline artifact persisted by this stage
        preds[name] = np.asarray(model.predict(X_test), dtype=float)
    mlp_meta = json.loads((models_dir / "mlp_meta.json").read_text())
    mlp_numeric: list[str] = mlp_meta["numeric_cols"]
    mlp_model = RentalMLP(
        n_numeric=len(mlp_numeric),
        embed_dim=cfg.mlp.embed_dim,
        hidden_dims=list(cfg.mlp.hidden_dims),
        dropout=cfg.mlp.dropout,
    )
    mlp_model.load_state_dict(torch.load(models_dir / "mlp.pt", weights_only=True))
    mlp_loaded = MLPRegressor(cfg, cfg.seed)
    mlp_loaded.model = mlp_model
    mlp_loaded.numeric_cols = mlp_numeric
    mlp_loaded.x_mean = np.asarray(mlp_meta["x_mean"], dtype=np.float64)
    mlp_loaded.x_std = np.asarray(mlp_meta["x_std"], dtype=np.float64)
    mlp_loaded.y_mean = float(mlp_meta["y_mean"])
    mlp_loaded.y_std = float(mlp_meta["y_std"])
    preds["mlp"] = np.asarray(mlp_loaded.predict(test_df[["hour", *selected]]), dtype=float)

    runs: dict[str, dict[str, float]] = {}
    for name, pred in preds.items():
        runs[name] = {
            "mae": mae(y_test, pred),
            "rmse": rmse(y_test, pred),
            "mape": mape(y_test, pred),
        }

    val_scores = {name: train_runs["val"][name]["mae"] for name in train_runs["val"]}
    champion = min(CANDIDATE_MODELS, key=lambda n: val_scores.get(n, float("inf")))
    ci, boot_deltas = paired_bootstrap_deltas(
        y_test, preds[champion], preds["seasonal_naive"], cfg.bootstrap_resamples, cfg.seed
    )

    comparison_fig = figures.model_comparison_figure(runs)
    save_html(comparison_fig, cfg.reports_dir / "figures" / "model_comparison.html")
    save_json(comparison_fig, cfg.reports_dir / "figures" / "model_comparison.json")

    residuals = y_test - preds[champion]
    heat_fig = figures.residual_heatmap_figure(test_df, residuals)
    save_html(heat_fig, cfg.reports_dir / "figures" / "residual_heatmap.html")
    save_json(heat_fig, cfg.reports_dir / "figures" / "residual_heatmap.json")

    rvf_fig = figures.residual_vs_fitted_figure(y_test, preds[champion])
    save_html(rvf_fig, cfg.reports_dir / "figures" / "residual_vs_fitted.html")
    save_json(rvf_fig, cfg.reports_dir / "figures" / "residual_vs_fitted.json")

    boot_fig = figures.bootstrap_ci_figure(boot_deltas, ci.to_dict())
    save_html(boot_fig, cfg.reports_dir / "figures" / "bootstrap_ci.html")
    save_json(boot_fig, cfg.reports_dir / "figures" / "bootstrap_ci.json")

    metrics_path = cfg.reports_dir / "metrics.json"
    _write_json(
        metrics_path,
        {
            **runs,
            "_meta": {
                "split": "test window: final test_weeks of the series, scored once per candidate",
                "champion": champion,
                "champion_selected_by": "lowest validation MAE (test never consulted)",
                "val_mae": val_scores,
                "mae_improvement_vs_floor_ci": ci.to_dict(),
                "hpo": train_runs["hpo"],
                "ablation": train_runs["ablation"],
                "limits": TEST_LIMITS,
            },
        },
    )

    metadata = {
        "protocol": (
            "Time-based split: the final 8 weeks of the 2011-2012 hourly series are "
            "the test window, scored once per candidate; the 8 weeks before it are "
            "validation (model selection, LightGBM HPO objective, MLP early stopping, "
            "ablation choice); everything earlier is training. Lag features read only "
            "the past. Paired bootstrap on the test window prices the champion-vs-floor "
            "MAE gap."
        ),
        "versions": _versions(),
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count() or 0,
            "torch_threads": torch.get_num_threads(),
        },
        "runtime": {
            "train_s": train_runs["train_runtime_s"],
            "evaluate_s": round(time.perf_counter() - started, 3),
        },
        "seed": cfg.seed,
        "limits": TEST_LIMITS,
    }
    _write_json(cfg.reports_dir / "evaluation_metadata.json", metadata)
    log.info(
        "evaluate: test MAE floor=%.1f champion=%s %.1f | improvement +%.1f, "
        "95%% CI [%.1f, %.1f] significant=%s",
        runs["seasonal_naive"]["mae"],
        champion,
        runs[champion]["mae"],
        ci.point,
        ci.lo,
        ci.hi,
        ci.significant_95,
    )
    return metrics_path


def _versions() -> dict[str, str]:
    import lightgbm
    import optuna
    import plotly
    import sklearn

    return {
        "python": platform.python_version(),
        "tabular_ml_lifecycle": tabular_ml_lifecycle.__version__,
        "scikit-learn": sklearn.__version__,
        "lightgbm": lightgbm.__version__,
        "optuna": optuna.__version__,
        "torch": torch.__version__,
        "plotly": plotly.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
