"""Validated configuration for the tabular ML + DL lifecycle pipeline.

Playbook convention (ADR-0002): tunable numbers live in pydantic config
models, not as module-level constants. ``LifecycleConfig`` is the single
source of truth for data preparation, feature selection, training and
evaluation.
"""

from pathlib import Path

import pandas as pd  # re-exported (covered by the root pandas.* ignore_missing_imports)
import yaml  # type: ignore[import-untyped]  # re-exported (no stubs in repo)
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator

__all__ = [
    "LifecycleConfig",
    "pd",  # pandas re-export: untyped here so consumers need no per-file ignore
    "yaml",  # same for pyyaml
]


class MLPConfig(PortfolioBaseModel):
    """Tabular MLP hyperparameters (PyTorch, hand-written training loop)."""

    hidden_dims: list[int] = Field(default=[64, 32], min_length=1)
    embed_dim: int = Field(default=8, ge=2)
    dropout: float = Field(default=0.2, ge=0.0, lt=1.0)
    weight_decay: float = Field(default=1e-4, ge=0.0)
    learning_rate: float = Field(default=1e-3, gt=0.0)
    batch_size: int = Field(default=256, ge=16)
    max_epochs: int = Field(default=150, ge=1)
    patience: int = Field(default=10, ge=1)
    huber_delta: float = Field(
        default=1.0,
        gt=0.0,
        description="Huber loss delta in standardized-y space (smooth MAE surrogate).",
    )


class LifecycleConfig(PortfolioBaseModel):
    """Configuration for the full lifecycle pipeline (prepare → report)."""

    # Data
    seed: int = Field(default=42, description="Global random seed (synthetic, split, HPO, torch).")
    data_source: str = Field(
        default="uci",
        pattern="^(uci|synthetic)$",
        description="'uci' = UCI Bike Sharing zip (real track); 'synthetic' = CI path.",
    )
    uci_source: str = Field(
        default="https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip",
        description="Canonical zip (http(s) fetched; local path accepted for tests).",
    )
    uci_sha256: str = Field(
        default="b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401",
        description="Expected sha256 of the UCI zip (verified on fetch).",
    )
    n_days_synthetic: int = Field(
        default=728, ge=120, description="Days of hourly history from the synthetic CI generator."
    )
    val_weeks: int = Field(
        default=8, ge=1, description="Validation window: weeks before the test window."
    )
    test_weeks: int = Field(
        default=8, ge=1, description="Scored-once test window: final weeks of the series."
    )
    lag_hours: list[int] = Field(
        default=[1, 24, 168],
        min_length=1,
        description="Past-only lag features on the rental count.",
    )

    # Feature selection
    corr_threshold: float = Field(
        default=0.9, gt=0.0, lt=1.0, description="|r| above which the lower-MI member is pruned."
    )

    # Models
    ridge_alpha: float = Field(default=1.0, gt=0.0)
    rf_n_estimators: int = Field(default=300, ge=10)
    rf_max_depth: int | None = Field(default=None, ge=1)
    rf_min_samples_leaf: int = Field(default=1, ge=1)
    hpo_trials: int = Field(default=50, ge=5, description="Optuna trial cap for LightGBM HPO.")
    hpo_time_budget_s: int = Field(
        default=240, ge=10, description="Optuna study timeout (seconds) — the binding budget."
    )
    lgbm_n_estimators: int = Field(
        default=1500, ge=10, description="Round cap; early stopping picks the rest."
    )
    lgbm_early_stopping: int = Field(default=50, ge=5)
    mlp: MLPConfig = Field(default_factory=MLPConfig)

    # Evaluation
    bootstrap_resamples: int = Field(default=2000, ge=100)
    learning_curve_fractions: list[float] = Field(default=[0.2, 0.4, 0.6, 0.8, 1.0], min_length=2)

    # Artifact locations
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")

    @field_validator("lag_hours")
    @classmethod
    def _lags_positive_distinct(cls, v: list[int]) -> list[int]:
        if any(k <= 0 for k in v):
            raise ValueError("lag_hours must be positive (past-only lags)")
        return sorted(set(v))

    @field_validator("learning_curve_fractions")
    @classmethod
    def _fractions_in_unit_interval(cls, v: list[float]) -> list[float]:
        if any(f <= 0.0 or f > 1.0 for f in v):
            raise ValueError("learning_curve_fractions must lie in (0, 1]")
        if v != sorted(v):
            raise ValueError("learning_curve_fractions must be sorted ascending")
        return v

    @property
    def max_lag(self) -> int:
        """Largest lag horizon — the first train rows sacrificed to NaN lags."""
        return max(self.lag_hours)
