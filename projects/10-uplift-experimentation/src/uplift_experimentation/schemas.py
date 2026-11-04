"""Typed contracts for this project (ADR-0002)."""

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


class PowerRead(PortfolioBaseModel):
    """Analytic power-analysis read for the measured effect."""

    p_treated: float = Field(ge=0.0, le=1.0)
    p_control: float = Field(ge=0.0, le=1.0)
    effect: float = Field(description="Measured absolute effect driving the calculation.")
    n_per_arm: int = Field(
        ge=1, description="Required customers per arm (two-sided two-proportion)."
    )
    n_total: int = Field(ge=2, description="2 x n_per_arm.")
    actual_per_arm: int = Field(ge=1, description="Customers per arm actually available.")
    sufficient: bool = Field(description="True when the actual experiment meets the requirement.")
