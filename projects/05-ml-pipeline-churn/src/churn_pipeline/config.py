"""Validated configuration for the churn pipeline.

Playbook convention: tunable numbers live in pydantic config models, not as
module-level constants. ``ChurnConfig`` is the single source of truth for
data preparation, model training and evaluation.
"""

from pathlib import Path
from typing import Any

import pandas as pd  # re-exported (covered by the root pandas.* ignore_missing_imports)
import yaml  # type: ignore[import-untyped]  # re-exported (no stubs in repo)
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]  # re-exported

__all__ = [
    "ChurnConfig",
    "pd",  # pandas re-export: untyped here so consumers need no per-file ignore
    "threadpool_limits",  # same for threadpoolctl
    "yaml",  # same for pyyaml
]


def _default_threshold_grid() -> list[float]:
    """41-point grid over the unit interval (0.00, 0.025, ..., 1.00)."""
    return [round(i / 40, 3) for i in range(41)]


class ChurnConfig(PortfolioBaseModel):
    """Configuration for the full churn pipeline (prepare → train → evaluate)."""

    # Data
    n_samples: int = Field(default=5_000, ge=200, description="Rows from the synthetic generator.")
    seed: int = Field(default=42, description="Global random seed (data + split + CV).")
    test_frac: float = Field(
        default=0.2,
        gt=0.0,
        lt=0.5,
        description="Stratified holdout fraction (temporal split not applicable to this data).",
    )
    data_source: str = Field(
        default="telco",
        pattern="^(telco|synthetic)$",
        description="'telco' = IBM telco churn (real-data primary track); 'synthetic' = CI path.",
    )
    telco_source: str = Field(
        default="https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv",
        description="Canonical CSV (http(s) fetched; local path accepted for tests).",
    )
    telco_sha256: str = Field(
        default="16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91",
        description="Expected sha256 of the telco CSV (verified on fetch; empty = skip).",
    )

    # Model selection
    c_grid: list[float] = Field(
        default=[0.01, 0.1, 1.0, 10.0],
        min_length=1,
        description="LogisticRegression C values swept by GridSearchCV (wave-2 baseline row).",
    )
    cv_folds: int = Field(default=3, ge=2, description="StratifiedKFold folds for grid search.")
    model_family: str = Field(
        default="auto",
        pattern="^(auto|logreg|histgb|xgboost|lightgbm)$",
        description="'auto' runs Optuna selection; otherwise the production config to train.",
    )
    model_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Selected classifier hyperparameters (production config, written by train).",
    )
    hpo_trials: int = Field(default=25, ge=5, description="Optuna trials for model selection.")
    hpo_objective: str = Field(
        default="cost",
        pattern="^(cost|f1)$",
        description="'cost' = CV business cost at fp_cost/fn_cost with per-trial threshold "
        "tuning; 'f1' = CV F1.",
    )
    calib_frac: float = Field(
        default=0.2,
        gt=0.0,
        lt=0.5,
        description="Fraction of training carved out for isotonic calibration only.",
    )

    # Evaluation / business layer
    threshold_grid: list[float] = Field(
        default_factory=_default_threshold_grid,
        min_length=2,
        description="Decision thresholds swept by the business-cost curve.",
    )
    fp_cost: float = Field(
        default=1.0, gt=0.0, description="Cost of one false positive (churn alarm)."
    )
    fn_cost: float = Field(
        default=5.0, gt=0.0, description="Cost of one missed churner (lost customer)."
    )
    calibration_bins: int = Field(default=10, ge=2, description="Bins for the calibration curve.")

    # Feature engineering
    cap_quantile_low: float = Field(
        default=0.01, gt=0.0, lt=0.5, description="Lower quantile for OutlierCapper."
    )
    cap_quantile_high: float = Field(
        default=0.99, gt=0.5, lt=1.0, description="Upper quantile for OutlierCapper."
    )

    # Artifact locations
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")

    @field_validator("c_grid")
    @classmethod
    def _c_grid_positive(cls, v: list[float]) -> list[float]:
        if any(c <= 0 for c in v):
            raise ValueError("c_grid values must be positive")
        return v

    @field_validator("threshold_grid")
    @classmethod
    def _thresholds_in_unit_interval(cls, v: list[float]) -> list[float]:
        if any(t < 0.0 or t > 1.0 for t in v):
            raise ValueError("threshold_grid values must lie in [0, 1]")
        if v != sorted(v):
            raise ValueError("threshold_grid must be sorted ascending")
        return v

    @property
    def holdout_rows(self) -> int:
        """Expected holdout size (informational; the split derives it exactly)."""
        return round(self.n_samples * self.test_frac)
