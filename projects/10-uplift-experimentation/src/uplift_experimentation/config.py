"""Validated configuration for the uplift & experimentation pipeline.

Playbook convention: tunable numbers live in pydantic config models, not as
module-level constants. ``UpliftConfig`` is the single source of truth for
data preparation, modeling and evaluation; every field mirrors params.yaml.
"""

from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]  # re-exported (no stubs in repo)
import yaml  # type: ignore[import-untyped]  # re-exported (no stubs in repo)
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator, model_validator
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]  # re-exported

__all__ = [
    "UpliftConfig",
    "pd",  # pandas re-export: untyped here so consumers need no per-file ignore
    "threadpool_limits",  # same for threadpoolctl
    "yaml",  # same for pyyaml
]


class UpliftConfig(PortfolioBaseModel):
    """Configuration for the full uplift pipeline (prepare → train → evaluate)."""

    # Data
    seed: int = Field(default=42, description="Global random seed (split + cross-fitting).")
    hillstrom_source: str = Field(
        default="http://minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv",
        description="Canonical Hillstrom CSV (author's site; http(s) fetched or local path).",
    )
    hillstrom_sha256: str = Field(
        default="0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece",
        description="Expected sha256 of the Hillstrom CSV (verified on fetch; empty = skip).",
    )
    treatment_segment: str = Field(
        default="Mens E-Mail",
        pattern="^(Mens E-Mail|Womens E-Mail)$",
        description="Campaign arm analyzed as treatment (vs 'No E-Mail' control).",
    )
    control_segment: str = Field(
        default="No E-Mail", pattern="^No E-Mail$", description="Holdout control arm."
    )

    # Campaign cost model (documented in DESIGN.md)
    revenue_per_conversion: float = Field(
        default=114.0,
        gt=0.0,
        description="Revenue ($) per incremental conversion; grounded in the measured mean "
        "spend of converters (~$114 AOV in the snapshot). This is revenue, not margin — "
        "the snapshot exposes no COGS, so profit here = revenue - email cost.",
    )
    cost_per_email: float = Field(
        default=0.01, gt=0.0, description="Marginal cost ($) of one email send."
    )

    # CUPED
    cuped_covariate: str = Field(
        default="log_history",
        pattern="^(log_history|history)$",
        description="Pre-period covariate.",
    )
    cuped_extra_covariates: list[str] = Field(
        default_factory=lambda: ["recency"],
        description="Additional strictly pre-treatment covariates adjusted alongside "
        "``cuped_covariate`` in the multivariate CUPED read (additive read; the "
        "univariate ``_meta.cuped`` metrics keep their current meaning and values).",
    )

    # Uplift models
    cv_folds: int = Field(default=5, ge=2, le=10, description="Cross-fitting folds for OOF scores.")

    # Power analysis
    alpha: float = Field(default=0.05, gt=0.0, lt=0.5, description="Two-sided significance level.")
    power: float = Field(default=0.8, gt=0.5, lt=1.0, description="Desired statistical power.")

    # Policy evaluation
    budget_fractions: list[float] = Field(
        default_factory=lambda: [
            0.05,
            0.1,
            0.15,
            0.2,
            0.25,
            0.3,
            0.4,
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
            1.0,
        ],
        min_length=2,
        description="Budget fractions where profit is evaluated per policy.",
    )
    policy_budget: float = Field(
        default=0.25, gt=0.0, lt=1.0, description="Budget fraction for the recommended policy."
    )
    n_deciles: int = Field(
        default=10, ge=2, le=20, description="Deciles for uplift-binning checks."
    )

    # Bootstrap uncertainty + cost sensitivity
    bootstrap_reps: int = Field(
        default=1000, ge=100, description="Paired-bootstrap replications for Qini/profit CIs."
    )
    cost_grid: list[float] = Field(
        default_factory=lambda: [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5],
        min_length=2,
        description="cost_per_email values for the profit sensitivity sweep.",
    )

    # Artifact locations
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")

    @field_validator("cuped_extra_covariates")
    @classmethod
    def _extra_covariates_valid(cls, v: list[str]) -> list[str]:
        if not v or any(not c for c in v):
            raise ValueError("cuped_extra_covariates must be non-empty names")
        return v

    @model_validator(mode="after")
    def _cuped_covariates_distinct(self) -> "UpliftConfig":
        if self.cuped_covariate in self.cuped_extra_covariates:
            raise ValueError("cuped_extra_covariates must not repeat cuped_covariate")
        return self

    @field_validator("budget_fractions")
    @classmethod
    def _budgets_in_unit_interval(cls, v: list[float]) -> list[float]:
        if any(f <= 0.0 or f > 1.0 for f in v):
            raise ValueError("budget_fractions must lie in (0, 1]")
        if v != sorted(v):
            raise ValueError("budget_fractions must be sorted ascending")
        return v

    @field_validator("cost_grid")
    @classmethod
    def _cost_grid_positive_sorted(cls, v: list[float]) -> list[float]:
        if any(c <= 0.0 for c in v):
            raise ValueError("cost_grid must be positive")
        if v != sorted(v):
            raise ValueError("cost_grid must be sorted ascending")
        return v

    @property
    def feature_cols(self) -> list[str]:
        """Pre-treatment covariates the uplift models may use (no leakage)."""
        return [
            "recency",
            "history",
            "log_history",
            "mens",
            "womens",
            "newbie",
            "channel",
            "zip_code",
        ]
