"""Multi-treatment uplift: per-arm scores, the best-arm policy, model-estimated evaluation.

Extension of the committed two-arm read (DESIGN.md). Each campaign arm is
scored against the shared ``No E-Mail`` control with a cross-fitted T-learner
(``models.cross_fit_arm_uplift``), and a **best-arm policy** recommends, per
customer, the arm with the highest estimated uplift — or no send when both arm
scores are <= 0 (ties also resolve to no send: no strict winner, no email).

Honesty convention: no randomized assignment realizes the recommended arm mix,
so the policy-level multi-arm evaluation is **model-estimated** throughout —
the incremental conversions of a targeted set are the summed predicted uplift
of the arm each customer is assigned. These are planning numbers, not
counterfactual claims. The only arm-level *causal* reads stay empirical: the
per-arm Qini/A-B contrasts computed on the randomized arm-vs-control pairs.
"""

from typing import Any

import numpy as np

from uplift_experimentation.qini import (
    incremental_at_full,
    qini_coefficient,
    qini_points,
    trapezoid,
)

# Segment vocabulary (mirrors data.SEGMENTS; kept local so this module stays
# importable without the polars-based data layer).
MENS_SEGMENT = "Mens E-Mail"
WOMENS_SEGMENT = "Womens E-Mail"
CONTROL_SEGMENT = "No E-Mail"

ARMS: tuple[tuple[str, str], ...] = (("mens", MENS_SEGMENT), ("womens", WOMENS_SEGMENT))
ARM_NONE = "none"
RECOMMENDATION_LABELS = ("mens", "womens", ARM_NONE)

# Multi-arm targeting policies compared in reports/metrics.json (model-estimated
# read on the three-arm frame; "single_arm"/"random" also carry a
# "two_arm_reference" with the committed empirical two-arm numbers).
MULTI_ARM_POLICIES = [
    "best_arm",
    "single_arm",
    "random",
    "mail_everyone_mens",
    "mail_everyone_womens",
]


def recommend_arm(uplift_mens: np.ndarray, uplift_womens: np.ndarray) -> np.ndarray:
    """Recommended arm per customer: argmax(uplift_mens, uplift_womens, 0).

    "mens"/"womens" only when that arm's score is strictly greater than the
    other's AND positive; "none" when both scores are <= 0 or when the two
    scores tie exactly (no strict winner -> no send).
    """
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    if u_m.shape != u_w.shape:
        raise ValueError("uplift arrays must align")
    out = np.full(u_m.shape, ARM_NONE, dtype="<U6")  # "womens" is 6 chars
    out[(u_m > u_w) & (u_m > 0.0)] = "mens"
    out[(u_w > u_m) & (u_w > 0.0)] = "womens"
    return out


def arm_shares(recommended: np.ndarray) -> dict[str, float]:
    """Shares of the recommended arms (mens/womens/none); they sum to 1 by construction."""
    rec = np.asarray(recommended)
    if rec.size == 0:
        raise ValueError("empty recommendation array")
    unknown = set(rec.tolist()) - set(RECOMMENDATION_LABELS)
    if unknown:
        raise ValueError(f"unexpected arm labels: {sorted(unknown)}")
    return {label: float(np.mean(rec == label)) for label in RECOMMENDATION_LABELS}


def assigned_uplift(
    uplift_mens: np.ndarray, uplift_womens: np.ndarray, recommended: np.ndarray
) -> np.ndarray:
    """Per-row MODEL-ESTIMATED incremental conversion under the recommended arm."""
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    rec = np.asarray(recommended)
    return np.where(rec == "mens", u_m, np.where(rec == "womens", u_w, 0.0))


def estimated_qini_curve(estimated: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(fractions, summed estimated uplift) targeting top scores first.

    This is the model-estimated analogue of ``qini.qini_points``: no arm
    contrast is involved, the curve simply accumulates the predicted uplift of
    the targeted rows. Includes (0, 0); ends at f=1 with the full-send total.
    """
    est = np.asarray(estimated, dtype=float)
    order = np.argsort(-est, kind="stable")
    inc = np.concatenate([[0.0], np.cumsum(est[order])])
    fractions = np.concatenate([[0.0], (np.arange(len(est)) + 1) / len(est)])
    return fractions, inc


def estimated_qini_coefficient(estimated: np.ndarray) -> float:
    """Area between the model-estimated curve and its random line (endpoint/2)."""
    fractions, inc = estimated_qini_curve(estimated)
    return float(trapezoid(fractions, inc) - inc[-1] / 2.0)


def multi_arm_policy_curves(
    uplift_mens: np.ndarray, uplift_womens: np.ndarray
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Model-estimated (fraction, incremental) curves for the multi-arm policies.

    - ``best_arm``: sorted per-row estimated uplift under the recommended arm.
    - ``single_arm``: Mens emails to the top ``uplift_mens`` scores (the binary
      model policy, evaluated with the same model-estimated machinery).
    - ``random``: straight line to ``best_arm``'s full-send total — the
      model-estimated random baseline (Qini 0 by construction).
    - ``mail_everyone_mens`` / ``mail_everyone_womens``: straight lines to each
      arm's full-send estimated total.
    """
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    est = assigned_uplift(u_m, u_w, recommend_arm(u_m, u_w))
    fr_best, inc_best = estimated_qini_curve(est)
    fr_m, inc_m = estimated_qini_curve(u_m)
    return {
        "best_arm": (fr_best, inc_best),
        "single_arm": (fr_m, inc_m),
        "random": (np.array([0.0, 1.0]), np.array([0.0, float(inc_best[-1])])),
        "mail_everyone_mens": (np.array([0.0, 1.0]), np.array([0.0, float(u_m.sum())])),
        "mail_everyone_womens": (np.array([0.0, 1.0]), np.array([0.0, float(u_w.sum())])),
    }


def per_arm_qini_read(
    segment: np.ndarray, outcome: np.ndarray, uplift_mens: np.ndarray, uplift_womens: np.ndarray
) -> dict[str, dict[str, Any]]:
    """Empirical per-arm Qini read on the randomized arm-vs-control pairs.

    For each arm: the rows of that arm plus the control, the arm indicator as
    treatment, and that arm's uplift score — the exact analogue of the binary
    two-arm read. These are the causal arm-level contrasts; the policy-level
    multi-arm numbers remain model-estimated.
    """
    seg = np.asarray(segment)
    y = np.asarray(outcome, dtype=float)
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    reads: dict[str, dict[str, Any]] = {}
    for arm, seg_name in ARMS:
        score = u_m if arm == "mens" else u_w
        mask = np.isin(seg, [seg_name, CONTROL_SEGMENT])
        t_arm = (seg[mask] == seg_name).astype(int)
        y_arm = y[mask]
        fr, inc = qini_points(t_arm, y_arm, score[mask])
        reads[arm] = {
            "n_rows": int(mask.sum()),
            "n_arm": int(t_arm.sum()),
            "n_control": int((1 - t_arm).sum()),
            "qini_coefficient": qini_coefficient(t_arm, y_arm, score[mask]),
            "incremental_conversions_full": incremental_at_full(t_arm, y_arm),
            "curve": (fr, inc),
        }
    return reads


def bootstrap_multi_arm_stats(
    uplift_mens: np.ndarray,
    uplift_womens: np.ndarray,
    segment: np.ndarray,
    outcome: np.ndarray,
    *,
    budget: float,
    n_total: int,
    revenue_per_conversion: float,
    cost_per_email: float,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Paired row bootstrap of the multi-arm read (one shared resample per rep).

    Policy-level quantities are MODEL-ESTIMATED (summed predicted uplift, one
    email per targeted customer): per-policy profit at the budget fraction,
    full-send incremental totals, and Qini coefficients for the curving
    policies (``best_arm``, ``single_arm``; the straight-line policies sit on
    the random line by construction). Arm-level quantities stay EMPIRICAL:
    per-arm Qini coefficients and full-send incremental conversions recomputed
    on the resampled arm-vs-control pairs. Deterministic under ``seed``.
    """
    u_m = np.asarray(uplift_mens, dtype=float)
    u_w = np.asarray(uplift_womens, dtype=float)
    seg = np.asarray(segment)
    y = np.asarray(outcome, dtype=float)
    n = len(y)
    rng = np.random.default_rng(seed)

    qini_b: dict[str, list[float]] = {p: [] for p in ("best_arm", "single_arm")}
    profit_b: dict[str, list[float]] = {p: [] for p in MULTI_ARM_POLICIES}
    inc_b: dict[str, list[float]] = {p: [] for p in MULTI_ARM_POLICIES}
    arm_qini_b: dict[str, list[float]] = {arm: [] for arm, _ in ARMS}
    arm_inc_b: dict[str, list[float]] = {arm: [] for arm, _ in ARMS}

    def budget_point(estimated: np.ndarray) -> tuple[float, float, float, float]:
        """(profit at budget, incremental at budget, full-send total, qini) for a curve."""
        fr, inc = estimated_qini_curve(estimated)
        k = int(np.argmin(np.abs(fr - budget)))
        profit = inc[k] * revenue_per_conversion - fr[k] * n_total * cost_per_email
        qini = float(trapezoid(fr, inc) - inc[-1] / 2.0)
        return float(profit), float(inc[k]), float(inc[-1]), qini

    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        um, uw, seg_b, y_b = u_m[idx], u_w[idx], seg[idx], y[idx]
        est = assigned_uplift(um, uw, recommend_arm(um, uw))

        profit, _inc_budget, inc_full, qini = budget_point(est)
        profit_b["best_arm"].append(profit)
        inc_b["best_arm"].append(inc_full)
        qini_b["best_arm"].append(qini)
        # Random baseline: straight line to this resample's best-arm total.
        profit_b["random"].append(
            budget * inc_full * revenue_per_conversion - budget * n_total * cost_per_email
        )
        inc_b["random"].append(inc_full)

        profit, _inc_budget, inc_full, qini = budget_point(um)
        profit_b["single_arm"].append(profit)
        inc_b["single_arm"].append(inc_full)
        qini_b["single_arm"].append(qini)

        for policy, u in (("mail_everyone_mens", um), ("mail_everyone_womens", uw)):
            total = float(u.sum())
            profit_b[policy].append(
                budget * total * revenue_per_conversion - budget * n_total * cost_per_email
            )
            inc_b[policy].append(total)

        for arm, seg_name in ARMS:
            score = um if arm == "mens" else uw
            mask = np.isin(seg_b, [seg_name, CONTROL_SEGMENT])
            t_arm = (seg_b[mask] == seg_name).astype(int)
            y_arm = y_b[mask]
            arm_qini_b[arm].append(qini_coefficient(t_arm, y_arm, score[mask]))
            arm_inc_b[arm].append(incremental_at_full(t_arm, y_arm))

    return {
        "qini": {p: np.asarray(v) for p, v in qini_b.items()},
        "profit_at_budget": {p: np.asarray(v) for p, v in profit_b.items()},
        "incremental_full": {p: np.asarray(v) for p, v in inc_b.items()},
        "arm_qini": {a: np.asarray(v) for a, v in arm_qini_b.items()},
        "arm_incremental_full": {a: np.asarray(v) for a, v in arm_inc_b.items()},
    }
