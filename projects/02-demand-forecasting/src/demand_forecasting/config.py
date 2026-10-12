"""Configuration for the demand-forecasting project.

Two layers, per platform convention (ADR-0002):
- :class:`DemandSettings`: environment-driven settings (seed, paths) — extends the
  platform :class:`portfolio_core.config.Settings`.
- :class:`ForecastConfig`: the forecast problem definition and modelling knobs.
  All constants live here, not in module-level variables.
"""

from datetime import date

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

    @field_validator("lags")
    @classmethod
    def _lags_sorted_positive(cls, v: list[int]) -> list[int]:
        if not v or any(lag < 1 for lag in v):
            raise ValueError("lags must be a non-empty list of positive integers")
        return sorted(set(v))

    @property
    def max_lag(self) -> int:
        """Largest lag; rows before this index per series are dropped."""
        return max(self.lags)
