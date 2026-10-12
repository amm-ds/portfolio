"""Validated configuration for the churn pipeline.

Playbook convention: tunable numbers live in pydantic config models, not as
module-level constants. ``ChurnConfig`` is the single source of truth for
data preparation, model training and evaluation.
"""

from pathlib import Path

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator


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

    # Model selection
    c_grid: list[float] = Field(
        default=[0.01, 0.1, 1.0, 10.0],
        min_length=1,
        description="LogisticRegression C values swept by GridSearchCV.",
    )
    cv_folds: int = Field(default=3, ge=2, description="StratifiedKFold folds for grid search.")

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
