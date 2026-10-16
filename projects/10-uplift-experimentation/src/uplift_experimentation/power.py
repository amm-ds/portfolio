"""Analytic sample-size calculation for two-proportion experiments.

Formula (standard normal approximation, two-sided test):

    n_per_arm = (z_{1-alpha/2} + z_{power})^2
                * [p1(1-p1) + p0(1-p0)] / (p1 - p0)^2

with p1, p0 the treated/control rates. This is the Fleiss-style variance form
(per-arm variance under each arm's own rate), conservative relative to the
pooled-rate form when rates are far from 0.5.
"""

from statistics import NormalDist

from uplift_experimentation.schemas import PowerRead

_Z = NormalDist()


def z_quantile(q: float) -> float:
    """Inverse standard-normal CDF via the stdlib (no scipy dependency)."""
    if not 0.0 < q < 1.0:
        raise ValueError("quantile must lie in (0, 1)")
    return _Z.inv_cdf(q)


def required_n_per_arm(p_treated: float, p_control: float, alpha: float, power: float) -> float:
    """Required customers per arm to detect |p_treated - p_control| at (alpha, power)."""
    if not 0.0 < p_treated < 1.0 or not 0.0 < p_control < 1.0:
        raise ValueError("rates must lie in (0, 1)")
    if not 0.0 < alpha < 0.5:
        raise ValueError("alpha must lie in (0, 0.5)")
    if not 0.5 < power < 1.0:
        raise ValueError("power must lie in (0.5, 1)")
    effect = abs(p_treated - p_control)
    if effect == 0.0:
        raise ValueError("effect size is zero: no finite sample size helps")
    z_a = z_quantile(1.0 - alpha / 2.0)
    z_b = z_quantile(power)
    variance_term = p_treated * (1.0 - p_treated) + p_control * (1.0 - p_control)
    return (z_a + z_b) ** 2 * variance_term / effect**2


def power_read(
    p_treated: float, p_control: float, alpha: float, power: float, actual_per_arm: int
) -> PowerRead:
    """Full power-analysis record for the measured effect."""
    n = required_n_per_arm(p_treated, p_control, alpha, power)
    return PowerRead(
        p_treated=p_treated,
        p_control=p_control,
        effect=p_treated - p_control,
        n_per_arm=int(np_ceil(n)),
        n_total=2 * int(np_ceil(n)),
        actual_per_arm=actual_per_arm,
        sufficient=actual_per_arm >= n,
    )


def np_ceil(x: float) -> int:
    """Ceil as int without importing numpy here."""
    import math

    return math.ceil(x)
