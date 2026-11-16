"""Cross-fitted DR/IPW evaluation of deterministic and stochastic email policies.

The policy rule is fixed by the existing out-of-fold uplift scores. Outcome
nuisances are also out-of-fold, and the randomized design supplies a known 1/3
assignment probability for each arm. Unlike ``multiarm.policies``, these values
use observed conversions and IPW corrections rather than summing predicted
uplift. They remain secondary to the committed two-arm Mens/control analysis.
"""

from typing import Any

import numpy as np

from uplift_experimentation.config import pd
from uplift_experimentation.multiarm import MULTI_ARM_POLICIES, recommend_arm
from uplift_experimentation.qini import ci_spans_zero, percentile_ci

ACTIONS = ("mens", "womens", "control")
VALUE_POLICIES = [*MULTI_ARM_POLICIES, "no_email"]


def build_policy_probabilities(
    uplift_mens: np.ndarray, uplift_womens: np.ndarray, budget: float
) -> dict[str, np.ndarray]:
    """Action probabilities per row for each policy, in ``ACTIONS`` order.

    Best-arm and single-arm target exactly ``round(budget * n)`` rows. Random
    targeting is represented as a stochastic policy: each customer has probability
    ``budget`` of receiving their recommended email, avoiding an arbitrary random
    draw in the point estimate. ``none`` recommendations allocate that mass to
    control. Every row sums to one.
    """
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    if u_m.shape != u_w.shape or u_m.ndim != 1 or len(u_m) == 0:
        raise ValueError("uplift arrays must be aligned, non-empty vectors")
    if not 0.0 < budget <= 1.0:
        raise ValueError("budget must lie in (0, 1]")
    n = len(u_m)
    k = int(np.rint(budget * n))
    recommended = recommend_arm(u_m, u_w)
    action_index = {action: i for i, action in enumerate(ACTIONS)}
    probs = {policy: np.zeros((n, len(ACTIONS)), dtype=float) for policy in VALUE_POLICIES}
    probs["no_email"][:, 2] = 1.0
    probs["mail_everyone_mens"][:, 0] = 1.0
    probs["mail_everyone_womens"][:, 1] = 1.0

    best_score = np.where(recommended == "none", 0.0, np.maximum(u_m, u_w))
    best_top = np.argsort(-best_score, kind="stable")[:k]
    for row in best_top:
        action = "control" if recommended[row] == "none" else str(recommended[row])
        probs["best_arm"][row, action_index[action]] = 1.0
    probs["best_arm"][:, 2] = 1.0 - probs["best_arm"].sum(axis=1)

    single_top = np.argsort(-u_m, kind="stable")[:k]
    probs["single_arm"][single_top, 0] = 1.0
    probs["single_arm"][:, 2] = 1.0 - probs["single_arm"][:, 0]

    for row, action in enumerate(recommended):
        if action != "none":
            probs["random"][row, action_index[str(action)]] = budget
    probs["random"][:, 2] = 1.0 - probs["random"].sum(axis=1)

    for policy, values in probs.items():
        if not np.allclose(values.sum(axis=1), 1.0) or (values < 0.0).any():
            raise ValueError(f"invalid action probabilities for {policy}")
    return probs


def dr_ipw_contributions(
    assignment: np.ndarray,
    outcome: np.ndarray,
    outcome_means: np.ndarray,
    policy_probabilities: np.ndarray,
    propensities: np.ndarray | float = 1.0 / 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-row augmented-IPW and IPW contributions to policy conversion value.

    ``policy_probabilities`` may encode deterministic or stochastic policies.
    DR is ``sum_a pi(a|X) mu_a(X)`` plus the observed-arm residual correction
    ``pi(A|X) / e(A|X) * (Y - mu_A(X))``. IPW drops the outcome-model terms.
    """
    a = np.asarray(assignment, dtype=int)
    y = np.asarray(outcome, dtype=float)
    mu = np.asarray(outcome_means, dtype=float)
    pi = np.asarray(policy_probabilities, dtype=float)
    if a.shape != y.shape or mu.shape != pi.shape or mu.shape[0] != len(y):
        raise ValueError("assignment, outcome, outcome means, and policy must align")
    if len(y) == 0 or mu.shape[1] != len(ACTIONS):
        raise ValueError("expected non-empty rows and Mens/Womens/control columns")
    if (a < 0).any() or (a >= len(ACTIONS)).any():
        raise ValueError("assignment labels must be 0, 1, or 2")
    e = np.broadcast_to(np.asarray(propensities, dtype=float), mu.shape)
    if not np.isfinite(e).all() or (e <= 0.0).any():
        raise ValueError("propensities must be finite and positive")
    rows = np.arange(len(y))
    observed_e = e[rows, a]
    observed_pi = pi[rows, a]
    residual = y - mu[rows, a]
    dr = (pi * mu).sum(axis=1) + observed_pi / observed_e * residual
    ipw = observed_pi / observed_e * y
    return dr, ipw


def _estimator_read(
    values: np.ndarray,
    boot_values: np.ndarray,
    baseline: np.ndarray,
    boot_baseline: np.ndarray,
    *,
    n: int,
    mailed_fraction: float,
    revenue: float,
    cost: float,
) -> dict[str, Any]:
    incremental = n * (float(values.mean()) - float(baseline.mean()))
    boot_incremental = n * (boot_values - boot_baseline)
    profit = incremental * revenue - n * mailed_fraction * cost
    boot_profit = boot_incremental * revenue - n * mailed_fraction * cost
    return {
        "conversion_rate": float(values.mean()),
        "conversion_rate_ci": list(percentile_ci(boot_values)),
        "incremental_conversions_vs_no_email": incremental,
        "incremental_conversions_vs_no_email_ci": list(percentile_ci(boot_incremental)),
        "profit": profit,
        "profit_ci": list(percentile_ci(boot_profit)),
    }


def policy_value_read(
    df: pd.DataFrame,
    *,
    budget: float,
    revenue_per_conversion: float,
    cost_per_email: float,
    n_boot: int,
    seed: int,
    cv_folds: int,
) -> dict[str, Any]:
    """Evaluate all multi-arm policies with paired DR/IPW row-bootstrap CIs."""
    assignment = np.select(
        [df["segment"].to_numpy() == "Mens E-Mail", df["segment"].to_numpy() == "Womens E-Mail"],
        [0, 1],
        default=2,
    )
    y = df["conversion"].to_numpy(dtype=float)
    mu = df[["mu_mens", "mu_womens", "mu_control"]].to_numpy(dtype=float)
    u_m = df["uplift_mens"].to_numpy(dtype=float)
    u_w = df["uplift_womens"].to_numpy(dtype=float)
    n = len(df)
    probabilities = build_policy_probabilities(u_m, u_w, budget)

    dr_rows: list[np.ndarray] = []
    ipw_rows: list[np.ndarray] = []
    mailed_fractions: list[float] = []
    for policy in VALUE_POLICIES:
        pi = probabilities[policy]
        dr, ipw = dr_ipw_contributions(assignment, y, mu, pi)
        dr_rows.append(dr)
        ipw_rows.append(ipw)
        mailed_fractions.append(float(1.0 - pi[:, 2].mean()))
    dr_values = np.column_stack(dr_rows)
    ipw_values = np.column_stack(ipw_rows)

    rng = np.random.default_rng(seed)
    dr_boot = np.empty((n_boot, len(VALUE_POLICIES)))
    ipw_boot = np.empty_like(dr_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        dr_boot[b] = dr_values[idx].mean(axis=0)
        ipw_boot[b] = ipw_values[idx].mean(axis=0)

    policies: dict[str, Any] = {}
    for i, policy in enumerate(VALUE_POLICIES):
        policies[policy] = {
            "mailed_fraction": mailed_fractions[i],
            "dr": _estimator_read(
                dr_values[:, i],
                dr_boot[:, i],
                dr_values[:, -1],
                dr_boot[:, -1],
                n=n,
                mailed_fraction=mailed_fractions[i],
                revenue=revenue_per_conversion,
                cost=cost_per_email,
            ),
            "ipw": _estimator_read(
                ipw_values[:, i],
                ipw_boot[:, i],
                ipw_values[:, -1],
                ipw_boot[:, -1],
                n=n,
                mailed_fraction=mailed_fractions[i],
                revenue=revenue_per_conversion,
                cost=cost_per_email,
            ),
        }

    pairs: dict[str, Any] = {}
    best_i = VALUE_POLICIES.index("best_arm")
    for other in ("single_arm", "random", "mail_everyone_mens", "mail_everyone_womens"):
        other_i = VALUE_POLICIES.index(other)
        pair: dict[str, Any] = {}
        for name, point, boot in (
            ("dr", dr_values, dr_boot),
            ("ipw", ipw_values, ipw_boot),
        ):
            point_diff = revenue_per_conversion * n * float(
                point[:, best_i].mean() - point[:, other_i].mean()
            ) - n * cost_per_email * (mailed_fractions[best_i] - mailed_fractions[other_i])
            boot_diff = revenue_per_conversion * n * (
                boot[:, best_i] - boot[:, other_i]
            ) - n * cost_per_email * (mailed_fractions[best_i] - mailed_fractions[other_i])
            ci = percentile_ci(boot_diff)
            pair[name] = {
                "profit_diff": point_diff,
                "profit_diff_ci": list(ci),
                "spans_zero": ci_spans_zero(ci),
            }
        pairs[f"best_arm - {other}"] = pair

    return {
        "method": "cross-fitted augmented-IPW (doubly robust) and IPW on observed outcomes",
        "outcome_models": f"{cv_folds}-fold out-of-fold arm-specific conversion classifiers",
        "propensity": "known randomized assignment: 1/3 per arm",
        "policy_budget": budget,
        "n_boot": n_boot,
        "seed": seed,
        "alpha": 0.05,
        "policies": policies,
        "pairs": pairs,
        "note": "Observed-outcome policy-value estimates, separate from summed-uplift planning. "
        "The paired row bootstrap holds the cross-fitted models and policy rules fixed; "
        "intervals omit model-refitting uncertainty.",
    }
