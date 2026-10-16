"""Typed contracts for this project (ADR-0002)."""

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


class ExperimentRead(PortfolioBaseModel):
    """Headline A/B read of the analyzed campaign (conversion outcome)."""

    n_treated: int = Field(ge=1)
    n_control: int = Field(ge=1)
    conv_rate_treated: float = Field(ge=0.0, le=1.0)
    conv_rate_control: float = Field(ge=0.0, le=1.0)
    ate: float = Field(description="Difference in conversion rates (treated - control).")
    ate_se: float = Field(gt=0.0, description="Standard error of the difference in means.")


class CupedRead(PortfolioBaseModel):
    """CUPED variance-reduction read on the experiment."""

    theta: float = Field(description="CUPED coefficient cov(Y, X) / var(X).")
    variance_reduction: float = Field(
        ge=0.0, lt=1.0, description="1 - var(Y_adj) / var(Y) on the pooled outcome."
    )
    ate: float = Field(
        description="CUPED-adjusted treatment-effect estimate (essentially unchanged)."
    )
    ate_se: float = Field(gt=0.0, description="CUPED-adjusted standard error (reduced).")
    se_reduction: float = Field(ge=0.0, lt=1.0, description="1 - se_adj / se_naive.")


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


class PolicyScore(PortfolioBaseModel):
    """Out-of-fold targeting scores for one customer row."""

    treatment: int = Field(ge=0, le=1)
    conversion: int = Field(ge=0, le=1)
    spend: float = Field(ge=0.0)
    visit: int = Field(ge=0, le=1)
    response: float = Field(description="Response-model score P(convert | X, treated).")
    t_learner: float = Field(description="T-learner uplift score mu1(X) - mu0(X).")
    x_learner: float = Field(description="X-learner uplift score.")


class PolicyResult(PortfolioBaseModel):
    """Evaluation of one targeting policy on out-of-fold scores."""

    policy: str
    qini_coefficient: float = Field(
        description="AUQC(policy) - AUQC(random) in conversions x fraction."
    )
    incremental_conversions: float = Field(
        description="Incremental conversions when targeting everyone."
    )
    profit_full: float = Field(description="Profit ($) when targeting everyone (may be negative).")
    profit_at_budget: float = Field(description="Profit ($) at the policy budget fraction.")
    profit_random_at_budget: float = Field(
        description="Random-targeting profit ($) at the same budget."
    )
    profit_delta_vs_random: float = Field(
        description="profit_at_budget - profit_random_at_budget ($)."
    )
