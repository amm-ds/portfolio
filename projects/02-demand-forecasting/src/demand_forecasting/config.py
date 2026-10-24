"""Configuration for the demand-forecasting project.

Two layers, per platform convention (ADR-0002):
- :class:`DemandSettings`: environment-driven settings (seed, paths) — extends the
  platform :class:`portfolio_core.config.Settings`.
- :class:`ForecastConfig`: the forecast problem definition and modelling knobs.
  All constants live here, not in module-level variables.
"""

from datetime import date
from typing import Any, Literal

from portfolio_core.config import Settings
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator


class DemandSettings(Settings):
    """Project settings: adds the dataset card identity to the platform settings."""

    dataset_name: str = Field(default="retail-hierarchy-synthetic")
    dataset_version: str = Field(default="1.0.0")
    dataset_source: str = Field(default="synthetic://retail_hierarchy")
    dataset_license: str = Field(default="CC0-1.0")
    dataset_snapshot_date: date = Field(default=date(2023, 12, 31))
    min_newest_date: str = Field(
        default="2024-06-01", description="DQ freshness gate: newest date must be >= this."
    )


class HGBTunedConfig(PortfolioBaseModel):
    """Production HGB hyperparameters — filled by Optuna HPO (see hpo.py).

    Defaults are the real best params found by a seeded study (56 complete
    trials, TPESampler seed 42, CV mean MAE 8.5291) on the synthetic panel;
    params.yaml mirrors them.
    """

    learning_rate: float = Field(default=0.08258768319962584, gt=0)
    max_iter: int = Field(default=190, ge=10)
    max_leaf_nodes: int = Field(default=25, ge=2)
    min_samples_leaf: int = Field(default=48, ge=1)
    l2_regularization: float = Field(default=0.0014656689866341544, ge=0)
    max_features: float = Field(default=0.5260286352147595, gt=0, le=1.0)

    def estimator_kwargs(self) -> dict[str, Any]:
        """Kwargs for :class:`~sklearn.ensemble.HistGradientBoostingRegressor`."""
        return self.model_dump()


class XGBTunedConfig(PortfolioBaseModel):
    """Production XGBoost hyperparameters — best of a seeded 25-trial study
    (CV mean MAE 8.5392, TPESampler seed 42); params.yaml mirrors them."""

    learning_rate: float = Field(default=0.04717052037625178, gt=0)
    n_estimators: int = Field(default=482, ge=10)
    max_depth: int = Field(default=4, ge=1)
    subsample: float = Field(default=0.7571172192068059, gt=0, le=1.0)
    colsample_bytree: float = Field(default=0.7962072844310213, gt=0, le=1.0)
    reg_lambda: float = Field(default=2.9140978279786215e-08, ge=0)

    def estimator_kwargs(self) -> dict[str, Any]:
        """Kwargs for :class:`~xgboost.XGBRegressor`."""
        return self.model_dump()


class LGBMTunedConfig(PortfolioBaseModel):
    """Production LightGBM hyperparameters — best of a seeded 25-trial study
    (CV mean MAE 8.4133, beats hgb_tuned's 8.5291); params.yaml mirrors them."""

    learning_rate: float = Field(default=0.1563510870813346, gt=0)
    n_estimators: int = Field(default=217, ge=10)
    num_leaves: int = Field(default=18, ge=2)
    min_child_samples: int = Field(default=139, ge=1)
    reg_lambda: float = Field(default=0.0002520721916536751, ge=0)

    def estimator_kwargs(self) -> dict[str, Any]:
        """Kwargs for :class:`~lightgbm.LGBMRegressor`."""
        return self.model_dump()


class ForecastConfig(PortfolioBaseModel):
    """Forecast problem definition: horizon, hierarchy shape, features, backtest."""

    n_days: int = Field(default=730, ge=30, description="History length per series.")
    n_stores: int = Field(default=4, ge=1)
    n_products: int = Field(default=6, ge=1)
    lags: list[int] = Field(default=[1, 7, 14], description="Lag features (days).")
    n_splits: int = Field(default=4, ge=2, description="Expanding-window CV folds.")
    gap: int = Field(default=7, ge=0, description="Embargo gap (days) between train and val.")
    min_train_size: int = Field(
        default=60, ge=1, description="Minimum training window (dates) for the first CV fold."
    )
    hgb_tuned: HGBTunedConfig = Field(
        default_factory=HGBTunedConfig, description="Production HGB params (from HPO)."
    )
    xgb_tuned: XGBTunedConfig = Field(
        default_factory=XGBTunedConfig, description="Production XGBoost params (from HPO)."
    )
    lgbm_tuned: LGBMTunedConfig = Field(
        default_factory=LGBMTunedConfig, description="Production LightGBM params (from HPO)."
    )
    seed: int = Field(
        default=42, description="Mirror of DemandSettings.seed for estimators built from config."
    )
    hpo_n_trials: int = Field(default=50, ge=5, description="Optuna trials for HPO.")
    temporal_epochs: int = Field(default=60, ge=5, description="Max epochs for temporal_net.")
    temporal_patience: int = Field(default=8, ge=1, description="Early-stop patience (epochs).")
    data_source: Literal["synthetic", "uci"] = Field(
        default="synthetic",
        description="Panel source. Synthetic stays the default so CI runs offline; "
        "'uci' activates the real-data track (network + ~45 MB download on first use).",
    )
    uci_n_stores: int = Field(default=8, ge=2, description="Top countries kept as stores.")
    uci_n_products: int = Field(default=200, ge=10, description="Top stock codes kept as products.")
    uci_checksum_sha256: str | None = Field(
        default="572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb",
        description="Pinned sha256 of the UCI zip snapshot (2026-10-12 download).",
    )
    uci_min_newest_date: str = Field(
        default="2010-12-01", description="DQ freshness floor for the UCI track."
    )
    # Multi-step (direct multi-horizon) track — protocol direct_multihorizon_v1.
    multistep_horizons: list[int] = Field(
        default=[1, 2, 3, 5, 7, 10, 14],
        description="Direct per-horizon models: one model per horizon h.",
    )
    multistep_n_origins: int = Field(
        default=20, ge=6, description="Weekly rolling origins (capped; evenly spaced)."
    )
    multistep_test_origins: int = Field(
        default=4, ge=1, description="Scored-once test origins (the LAST ones)."
    )
    multistep_window_days: int = Field(
        default=14, ge=1, description="Forecast window length per origin (days)."
    )
    service_levels: list[float] = Field(
        default=[0.8, 0.9, 0.95], description="Order-up-to service levels (decision metric)."
    )
    holding_cost: float = Field(
        default=0.25, gt=0, description="Assumed holding cost per leftover unit per cell."
    )
    stockout_cost: float = Field(
        default=4.0, gt=0, description="Assumed stockout penalty per unit short per cell."
    )
    bootstrap_reps: int = Field(
        default=2000, ge=100, description="Paired-bootstrap replications (multi-step track)."
    )

    @field_validator("lags")
    @classmethod
    def _lags_sorted_positive(cls, v: list[int]) -> list[int]:
        if not v or any(lag < 1 for lag in v):
            raise ValueError("lags must be a non-empty list of positive integers")
        return sorted(set(v))

    @field_validator("multistep_horizons")
    @classmethod
    def _horizons_sorted_positive(cls, v: list[int]) -> list[int]:
        if not v or any(h < 1 for h in v):
            raise ValueError("multistep_horizons must be a non-empty list of positive integers")
        return sorted(set(v))

    @property
    def max_lag(self) -> int:
        """Largest lag; rows before this index per series are dropped."""
        return max(self.lags)
