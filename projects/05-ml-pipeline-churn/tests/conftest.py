"""Shared fixtures: tiny validated config and messy synthetic frames."""

from pathlib import Path

import numpy as np
import pytest
from churn_pipeline.config import ChurnConfig, pd
from portfolio_core import synthetic


@pytest.fixture()
def small_cfg(tmp_path: Path) -> ChurnConfig:
    """Small, fast config with artifacts redirected into tmp_path."""
    return ChurnConfig(
        n_samples=400,
        seed=7,
        c_grid=[0.1, 1.0],
        cv_folds=2,
        hpo_trials=6,
        calib_frac=0.25,
        threshold_grid=[0.2, 0.4, 0.6, 0.8],
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
    )


@pytest.fixture()
def params_file(tmp_path: Path) -> Path:
    """Isolated params.yaml so HPO never rewrites the repo's production config."""
    path = tmp_path / "params.yaml"
    path.write_text("model_family: auto\nhpo_trials: 6\n")
    return path


@pytest.fixture()
def messy_frame() -> pd.DataFrame:
    """Tiny frame carrying the same messiness as the real generator."""
    return pd.DataFrame(
        {
            "age": [25.0, np.nan, 40.0, 9_999.0, 60.0],
            "tenure_months": [1.0, 12.0, 24.0, 36.0, np.nan],
            "monthly_charges": [50.0, 80.0, np.nan, 9_999.0, 100.0],
            "support_calls": [0.0, 1.0, np.nan, 5.0, 2.0],
            "contract": ["month-to-month", "one-year", "two-year", "month-to-month", "one-year"],
            "churned": [1, 0, 0, 1, 0],
        }
    )


@pytest.fixture()
def tiny_synthetic() -> pd.DataFrame:
    """Small real synthetic churn frame for integration tests."""
    return synthetic.churn(seed=7, n=200).to_pandas()
