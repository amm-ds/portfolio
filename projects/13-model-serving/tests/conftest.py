"""Shared fixtures: a tiny trained served model (seconds to fit, offline).

The fixture exercises the real path end to end — synthetic frame, feature
selection, seeded LightGBM fit, ONNX export, parity gate — at a scale tests
can afford. Everything downstream (service, parity tests) mounts the same
persisted artifacts.
"""

import json
import pickle
from pathlib import Path

import pytest
from model_serving.artifacts import check_parity, export_onnx, probe_grid, raw_onnx_predict
from model_serving.config import LGBMConfig, ServingConfig
from model_serving.data import TARGET_COL, make_synthetic_frame, split_windows
from model_serving.features import CANDIDATE_FEATURES, apply_split, build_features
from model_serving.lgbm import lgbm_estimator


def tiny_config(tmp: Path) -> ServingConfig:
    return ServingConfig(
        data_source="synthetic",
        champion_expected_test_mae=1.0,
        reproduction_tolerance=1e9,  # reproduction gate is the real pipeline's job
        lgbm=LGBMConfig(n_estimators=60, early_stopping=10, hpo_trials=5, hpo_time_budget_s=60),
        probe_grid_n=64,
        data_dir=tmp / "data",
        reports_dir=tmp / "reports",
    )


@pytest.fixture(scope="session")
def tiny_models(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """Fit a tiny served model on the synthetic twin; return model + models_dir + cfg."""
    tmp = tmp_path_factory.mktemp("tiny")
    cfg = tiny_config(tmp)
    # A 40-day frame leaves month_sin/month_cos near-constant: span >12 months
    # so every cyclical feature varies like the real year-long series.
    df = make_synthetic_frame(seed=7, n_days=400)
    windows = split_windows(len(df), val_weeks=1, test_weeks=1)
    featured = build_features(df, cfg.lag_hours, cfg.lag_mode)
    train_df, _, _ = apply_split(featured, windows, cfg.max_lag)

    # The service schema mirrors experiment 12's v2 committed contract; the tiny
    # fixture trains on exactly that column set (temp pruned in favor of atemp,
    # r > 0.9) so the artifact and schema agree regardless of tiny-data selection.
    selected = [c for c in CANDIDATE_FEATURES if c != "temp"]
    model = lgbm_estimator(cfg, cfg.seed, learning_rate=0.1, num_leaves=31)
    model.fit(train_df[selected], train_df[TARGET_COL].astype(float))

    models_dir = cfg.data_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    with (models_dir / "lightgbm.pkl").open("wb") as fh:
        pickle.dump(model, fh)
    (models_dir / "lgbm_meta.json").write_text(
        json.dumps(
            {
                "family": "lightgbm",
                "numeric_cols": selected,
                "best_iteration": int(getattr(model, "best_iteration_", 0) or 0),
                "n_estimators_cap": cfg.lgbm.n_estimators,
                "hpo_best_params": {},
            }
        )
    )
    export_onnx(model, len(selected), models_dir / "model.onnx", cfg.onnx_opset)
    return {"model": model, "models_dir": models_dir, "cfg": cfg, "selected": selected}


@pytest.fixture(scope="session")
def parity_checked(tiny_models: dict[str, object]) -> dict[str, object]:
    """The fixture model, with the ONNX parity gate already enforced."""
    cfg = tiny_models["cfg"]
    selected = tiny_models["selected"]
    model = tiny_models["model"]
    assert isinstance(cfg, ServingConfig)
    grid = probe_grid(cfg.probe_grid_n, cfg.seed, selected)  # type: ignore[arg-type]
    native = model.predict(grid[selected])  # type: ignore[union-attr,index]
    max_abs = check_parity(
        native,
        raw_onnx_predict(tiny_models["models_dir"], grid, selected),  # type: ignore[arg-type]
        cfg.parity_tolerance,
    )
    tiny_models["parity_max_abs"] = max_abs
    return tiny_models
