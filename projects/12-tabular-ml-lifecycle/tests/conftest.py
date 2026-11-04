"""Shared fixtures: tiny validated config and synthetic frames (no network)."""

from pathlib import Path

import pandas as pd
import pytest
from portfolio_core.schemas import DatasetContract
from tabular_ml_lifecycle.config import LifecycleConfig, MLPConfig
from tabular_ml_lifecycle.data import make_synthetic_frame


@pytest.fixture()
def small_cfg(tmp_path: Path) -> LifecycleConfig:
    """Small, fast config with artifacts redirected into tmp_path (synthetic CI path)."""
    return LifecycleConfig(
        seed=7,
        data_source="synthetic",
        n_days_synthetic=140,
        val_weeks=2,
        test_weeks=2,
        rf_n_estimators=10,
        hpo_trials=5,
        hpo_time_budget_s=60,
        lgbm_n_estimators=50,
        lgbm_early_stopping=10,
        mlp=MLPConfig(hidden_dims=[8], embed_dim=4, max_epochs=4, patience=2, batch_size=64),
        bootstrap_resamples=100,
        learning_curve_fractions=[0.5, 1.0],
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )


@pytest.fixture()
def small_frame() -> pd.DataFrame:
    """Two-season synthetic hourly frame for unit tests."""
    return make_synthetic_frame(seed=7, n_days=140)


@pytest.fixture()
def contract(small_frame: pd.DataFrame) -> DatasetContract:
    """Validate the DatasetContract schema round-trips on a real frame."""
    from tabular_ml_lifecycle.data import dataset_contract_for

    return dataset_contract_for(
        small_frame, "bike_sharing_hourly_synthetic", "synthetic://test", "MIT"
    )
