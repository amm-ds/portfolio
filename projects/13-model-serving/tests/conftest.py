"""Shared fixtures: a tiny trained champion (seconds to fit, offline).

The fixture exercises the real path end to end — synthetic frame, feature
selection, hand-written MLP loop, ONNX export, parity gate — at a scale tests
can afford. Everything downstream (service, parity tests) mounts the same
persisted artifacts.
"""

from pathlib import Path

import pytest
from model_serving.artifacts import check_parity, export_onnx, probe_grid, raw_onnx_predict
from model_serving.config import MLPConfig, ServingConfig
from model_serving.data import TARGET_COL, make_synthetic_frame, split_windows
from model_serving.features import CANDIDATE_FEATURES, apply_split, build_features
from model_serving.mlp import MLPRegressor


def tiny_config(tmp: Path) -> ServingConfig:
    return ServingConfig(
        data_source="synthetic",
        champion_expected_test_mae=1.0,
        reproduction_tolerance=1e9,  # reproduction gate is the real pipeline's job
        mlp=MLPConfig(
            hidden_dims=[8],
            embed_dim=4,
            dropout=0.1,
            learning_rate=1e-3,
            batch_size=64,
            max_epochs=15,
            patience=5,
        ),
        probe_grid_n=64,
        data_dir=tmp / "data",
        reports_dir=tmp / "reports",
    )


@pytest.fixture(scope="session")
def tiny_models(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """Fit a tiny champion on the synthetic twin; return reg + models_dir + cfg."""
    tmp = tmp_path_factory.mktemp("tiny")
    cfg = tiny_config(tmp)
    # A 40-day frame leaves month_sin/month_cos near-constant: the train-fitted
    # scaler then maps legal [-1, 1] probe inputs to huge standardized values
    # (the model is fine — the probe leaves the training envelope). Span >12
    # months so every cyclical feature varies like the real year-long series.
    df = make_synthetic_frame(seed=7, n_days=400)
    windows = split_windows(len(df), val_weeks=1, test_weeks=1)
    featured = build_features(df, cfg.lag_hours)
    train_df, val_df, _ = apply_split(featured, windows, cfg.max_lag)

    # The service schema mirrors experiment 12's committed contract; the tiny
    # fixture trains on exactly that column set (atemp pruned, r > 0.9) so the
    # artifact and schema agree regardless of what tiny-data selection finds.
    selected = [c for c in CANDIDATE_FEATURES if c != "atemp"]
    mlp_cols = ["hour", *selected]
    reg = MLPRegressor(cfg.mlp, cfg.seed)
    reg.fit(
        train_df[mlp_cols],
        train_df[TARGET_COL].astype(float),
        val_df[mlp_cols],
        val_df[TARGET_COL].astype(float),
        selected,
    )

    models_dir = cfg.data_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    assert reg.model is not None and reg.x_mean is not None and reg.x_std is not None
    import json

    import torch

    torch.save(reg.model.state_dict(), models_dir / "mlp.pt")
    (models_dir / "mlp_arch.json").write_text(
        json.dumps(
            {
                "hour_cardinality": 24,
                "n_numeric": len(selected),
                "embed_dim": cfg.mlp.embed_dim,
                "hidden_dims": list(cfg.mlp.hidden_dims),
                "dropout": cfg.mlp.dropout,
            }
        )
    )
    (models_dir / "mlp_meta.json").write_text(
        json.dumps(
            {
                "numeric_cols": selected,
                "x_mean": reg.x_mean.tolist(),
                "x_std": reg.x_std.tolist(),
                "y_mean": reg.y_mean,
                "y_std": reg.y_std,
                "best_epoch": reg.history.best_epoch,
                "epochs_run": reg.history.epochs_run,
            }
        )
    )
    export_onnx(reg.model, len(selected), models_dir / "model.onnx", cfg.onnx_opset)
    return {"reg": reg, "models_dir": models_dir, "cfg": cfg, "selected": selected}


@pytest.fixture(scope="session")
def parity_checked(tiny_models: dict[str, object]) -> dict[str, object]:
    """The fixture model, with the ONNX parity gate already enforced."""
    reg = tiny_models["reg"]
    cfg = tiny_models["cfg"]
    selected = tiny_models["selected"]
    assert isinstance(reg, MLPRegressor)
    assert isinstance(cfg, ServingConfig)
    grid = probe_grid(cfg.probe_grid_n, cfg.seed, selected)  # type: ignore[arg-type]
    max_abs = check_parity(
        reg.predict_scaled(grid),
        raw_onnx_predict(tiny_models["models_dir"], grid, selected),  # type: ignore[arg-type]
        cfg.parity_tolerance,
    )
    tiny_models["parity_max_abs"] = max_abs
    return tiny_models
