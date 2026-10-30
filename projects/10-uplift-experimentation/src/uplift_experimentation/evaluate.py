"""Evaluation: Qini ladder, profit frontier, CUPED + power reads, report.

Reads the cross-fitted scores from the train stage and produces every artifact
the report needs: per-policy Qini coefficients with paired-bootstrap CIs,
decile checks, profit under the campaign cost model (frontier + cost
sensitivity), the CUPED variance-reduction panel (univariate + multivariate),
the analytic power analysis, and the secondary multi-arm read (per-arm Qini,
best-arm policy, recommended-arm distribution) — plus the eight themed
figures (HTML + JSON).
"""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from portfolio_core.logging import get_logger
from portfolio_core.plotting import (
    add_takeaway,
    apply_theme,
    is_baseline_run,
    save_html,
    save_json,
    style_runs,
)
from portfolio_eval.report import EvalReport

from uplift_experimentation.config import UpliftConfig, pd
from uplift_experimentation.cuped import (
    cuped_adjust,
    cuped_adjust_multi,
    cuped_theta,
    cuped_theta_multi,
    effect_and_se,
    variance_reduction,
)
from uplift_experimentation.models import SCORE_POLICIES
from uplift_experimentation.multiarm import (
    ARMS,
    MULTI_ARM_POLICIES,
    arm_shares,
    assigned_uplift,
    bootstrap_multi_arm_stats,
    estimated_qini_coefficient,
    multi_arm_policy_curves,
    per_arm_qini_read,
    recommend_arm,
)
from uplift_experimentation.power import power_read
from uplift_experimentation.qini import (
    bootstrap_policy_stats,
    ci_spans_zero,
    incremental_at_full,
    percentile_ci,
    profit_curve,
    qini_coefficient,
    qini_points,
    uplift_by_decile,
)

log = get_logger(__name__)

BASELINE_POLICIES = ["random", "treat-everyone"]


# ---------------------------------------------------------------------------
# Evaluation reads
# ---------------------------------------------------------------------------


def evaluate_policies(
    cfg: UpliftConfig, df: pd.DataFrame
) -> tuple[dict[str, dict[str, float]], dict[str, tuple[np.ndarray, np.ndarray]]]:
    """Per-policy Qini + profit read; returns (metrics, curves) keyed by policy."""
    treatment = df["treatment"].to_numpy(dtype=int)
    outcome = df["conversion"].to_numpy(dtype=float)
    n_total = len(df)
    inc_all = incremental_at_full(treatment, outcome)
    curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    metrics: dict[str, dict[str, float]] = {}

    def profit_at(fr: np.ndarray, inc: np.ndarray, f: float) -> float:
        idx = int(np.argmin(np.abs(fr - f)))
        return float(
            profit_curve(
                np.array([fr[idx]]),
                np.array([inc[idx]]),
                n_total,
                cfg.revenue_per_conversion,
                cfg.cost_per_email,
            )[0]
        )

    for policy in SCORE_POLICIES + BASELINE_POLICIES:
        if policy == "random":
            fr = np.linspace(0.0, 1.0, 101)
            inc = fr * inc_all
        elif policy == "treat-everyone":
            fr = np.array([1.0])
            inc = np.array([inc_all])
        else:
            fr, inc = qini_points(treatment, outcome, df[policy].to_numpy(dtype=float))
        curves[policy] = (fr, inc)

        if policy in ("random", "treat-everyone"):
            qini = 0.0  # by construction, both sit on the random line
        else:
            qini = qini_coefficient(treatment, outcome, df[policy].to_numpy(dtype=float))
        prof_full = profit_at(np.array([1.0]), np.array([inc_all]), 1.0)
        if policy == "treat-everyone":
            prof_budget = float("nan")  # decision is taken at f=1 only
        else:
            prof_budget = profit_at(fr, inc, cfg.policy_budget)
        profit_random_budget = float(
            profit_curve(
                np.array([cfg.policy_budget]),
                np.array([cfg.policy_budget * inc_all]),
                n_total,
                cfg.revenue_per_conversion,
                cfg.cost_per_email,
            )[0]
        )
        metrics[policy] = {
            "qini_coefficient": qini,
            "incremental_conversions_full": float(inc_all),
            "profit_full": prof_full,
            "profit_at_budget": prof_budget,
            "profit_random_at_budget": profit_random_budget,
            "profit_delta_vs_random": prof_budget - profit_random_budget,
        }
    return metrics, curves


# ---------------------------------------------------------------------------
# Bootstrap uncertainty + cost sensitivity
# ---------------------------------------------------------------------------


def bootstrap_ci_read(
    cfg: UpliftConfig, df: pd.DataFrame
) -> tuple[dict[str, Any], dict[str, tuple[np.ndarray, np.ndarray]], np.ndarray]:
    """Paired bootstrap CIs for per-policy Qini / profit-at-budget + curve bands.

    One shared row-resample per replication across all policies, so every
    model-vs-model difference is paired on identical resamples. Returns
    (ci_meta for metrics.json, per-policy figure bands, band grid).
    """
    treatment = df["treatment"].to_numpy(dtype=int)
    outcome = df["conversion"].to_numpy(dtype=float)
    scores = {p: df[p].to_numpy(dtype=float) for p in SCORE_POLICIES}
    band_grid = np.linspace(0.0, 1.0, 101)
    boot_seed = cfg.seed + 999  # distinct stream from cross-fitting
    stats = bootstrap_policy_stats(
        treatment,
        outcome,
        scores,
        budget=cfg.policy_budget,
        n_total=len(df),
        revenue_per_conversion=cfg.revenue_per_conversion,
        cost_per_email=cfg.cost_per_email,
        n_boot=cfg.bootstrap_reps,
        seed=boot_seed,
        band_grid=band_grid,
    )

    ci_meta: dict[str, Any] = {
        "method": "paired row bootstrap of out-of-fold scores, percentile interval",
        "n_boot": cfg.bootstrap_reps,
        "seed": boot_seed,
        "alpha": 0.05,
        "policies": {},
        "pairs": {},
    }
    for policy in SCORE_POLICIES:
        ci_meta["policies"][policy] = {
            "qini_ci": list(percentile_ci(stats["qini"][policy])),
            "profit_at_budget_ci": list(percentile_ci(stats["profit_at_budget"][policy])),
        }
    for i, a in enumerate(SCORE_POLICIES):
        for b in SCORE_POLICIES[i + 1 :]:
            qini_diff = stats["qini"][a] - stats["qini"][b]
            profit_diff = stats["profit_at_budget"][a] - stats["profit_at_budget"][b]
            qini_ci = percentile_ci(qini_diff)
            profit_ci = percentile_ci(profit_diff)
            ci_meta["pairs"][f"{a} - {b}"] = {
                "qini_diff_ci": list(qini_ci),
                "qini_diff_spans_zero": ci_spans_zero(qini_ci),
                "profit_at_budget_diff_ci": list(profit_ci),
                "profit_at_budget_diff_spans_zero": ci_spans_zero(profit_ci),
            }

    # The recommended policy vs the two non-model baselines, on the same
    # paired resamples (T minus comparator throughout).
    t_policy = "t_learner"
    inc_all = incremental_at_full(treatment, outcome)
    fr_t, inc_t = qini_points(treatment, outcome, scores[t_policy])
    k_t = int(np.argmin(np.abs(fr_t - cfg.policy_budget)))
    t_point = float(
        profit_curve(
            np.array([fr_t[k_t]]),
            np.array([inc_t[k_t]]),
            len(df),
            cfg.revenue_per_conversion,
            cfg.cost_per_email,
        )[0]
    )
    random_point = float(
        profit_curve(
            np.array([cfg.policy_budget]),
            np.array([cfg.policy_budget * inc_all]),
            len(df),
            cfg.revenue_per_conversion,
            cfg.cost_per_email,
        )[0]
    )
    mail_point = float(
        profit_curve(
            np.array([1.0]),
            np.array([inc_all]),
            len(df),
            cfg.revenue_per_conversion,
            cfg.cost_per_email,
        )[0]
    )
    t_profit = stats["profit_at_budget"][t_policy]
    vs_random_ci = percentile_ci(t_profit - stats["random_profit_at_budget"])
    vs_mail_ci = percentile_ci(t_profit - stats["mail_everyone_profit_at_budget"])
    ci_meta["t_learner_vs_random"] = {
        "profit_at_budget_diff_ci": list(vs_random_ci),
        "spans_zero": ci_spans_zero(vs_random_ci),
        "point_diff": t_point - random_point,
    }
    ci_meta["t_learner_vs_mail_everyone"] = {
        "profit_at_budget_diff_ci": list(vs_mail_ci),
        "spans_zero": ci_spans_zero(vs_mail_ci),
        "point_diff": t_point - mail_point,
    }
    return ci_meta, stats["band"], band_grid


def cost_sensitivity_read(
    cfg: UpliftConfig,
    curves: dict[str, tuple[np.ndarray, np.ndarray]],
    best: str,
    n_total: int,
) -> dict[str, Any]:
    """How the profit-maximizing targeting fraction moves as sends get pricey.

    For each cost_per_email in cfg.cost_grid: the best budget fraction for the
    recommended policy, its profit, and the mail-everyone profit. Also the
    analytic break-even send cost at the policy budget — the answer to "at what
    cost does top-k beat mail-everyone?":

        c* = revenue * (inc(1) - inc(budget)) / (N * (1 - budget))
    """
    fr, inc = curves[best]
    inc_all = float(inc[-1])
    inc_budget = float(np.interp(cfg.policy_budget, fr, inc))
    fractions = np.asarray(cfg.budget_fractions, dtype=float)
    rows = []
    for cost in cfg.cost_grid:
        profits = profit_curve(
            fractions,
            np.interp(fractions, fr, inc),
            n_total,
            cfg.revenue_per_conversion,
            cost,
        )
        k = int(np.argmax(profits))
        mail_everyone = float(
            profit_curve(
                np.array([1.0]),
                np.array([inc_all]),
                n_total,
                cfg.revenue_per_conversion,
                cost,
            )[0]
        )
        rows.append(
            {
                "cost_per_email": float(cost),
                "profit_max_fraction": float(fractions[k]),
                "profit_at_max": float(profits[k]),
                "profit_mail_everyone": mail_everyone,
                "targeting_beats_mail_everyone": bool(profits[k] > mail_everyone),
            }
        )
    n_mail_budget = n_total * (1.0 - cfg.policy_budget)
    breakeven = cfg.revenue_per_conversion * (inc_all - inc_budget) / n_mail_budget
    return {
        "best_policy": best,
        "policy_budget": cfg.policy_budget,
        "rows": rows,
        "breakeven_cost_per_email": float(breakeven),
        "note": "profit = revenue - email cost; revenue_per_conversion is mean spend "
        "among converters (no COGS in the snapshot), so break-even costs are optimistic "
        "if true margin is lower than revenue.",
    }


def cost_sensitivity_figure(read: dict[str, Any], cfg: UpliftConfig) -> go.Figure:
    """Profit vs send cost: mail-everyone vs the recommended top-k policy."""
    fig = go.Figure()
    costs = [r["cost_per_email"] for r in read["rows"]]
    fig.add_scatter(
        x=costs,
        y=[r["profit_mail_everyone"] for r in read["rows"]],
        mode="lines+markers",
        name="mail everyone",
    )
    fig.add_scatter(
        x=costs,
        y=[r["profit_at_max"] for r in read["rows"]],
        mode="lines+markers",
        name=f"{read['best_policy']} @ {read['policy_budget']:.0%} budget",
    )
    fig.add_vline(
        x=read["breakeven_cost_per_email"],
        line_dash="dot",
        line_color="#64748b",
        annotation_text=f"break-even {read['breakeven_cost_per_email']:.2f} USD/email",
        annotation_position="top left",
    )
    # Label the reference send costs directly on the chart (audit: the grid
    # values lived only in the axis ticks). The break-even reference is
    # highlighted in amber — it is the decision threshold (the dotted vline
    # carries the full text).
    reference_costs = (0.01, 0.20, 0.30, 0.50)
    for cost in reference_costs:
        if not any(abs(r["cost_per_email"] - cost) < 1e-9 for r in read["rows"]):
            continue
        is_breakeven = abs(cost - read["breakeven_cost_per_email"]) < 0.02
        fig.add_annotation(
            # Log axis: plotly reads annotation x as log10(position).
            x=math.log10(cost),
            y=1.0,
            yref="paper",
            text=f"{cost:.2f}",
            showarrow=False,
            yanchor="bottom",
            yshift=4,
            font={"size": 12, "color": "#fbbf24" if is_breakeven else "#cbd5e1"},
        )
    apply_theme(fig)
    style_runs(fig, best=read["best_policy"])
    fig.update_layout(
        title=(
            f"Profit vs send cost: all vs top-{read['policy_budget']:.0%} ({read['best_policy']})"
        ),
        xaxis_title="cost per email (USD, log scale)",
        yaxis_title="profit (USD)",
        xaxis_type="log",
    )
    add_takeaway(
        fig,
        f"best fraction vs mail-everyone, send cost {costs[0]:.2f}-{costs[-1]:.2f} "
        f"USD (log x); dotted = break-even {read['breakeven_cost_per_email']:.2f}",
    )
    return fig


def cuped_outcome_read(cfg: UpliftConfig, df: pd.DataFrame, outcome: str) -> dict[str, float]:
    """CUPED on one outcome with the pre-period spend covariate.

    Conversion is the primary read per the design: prior-year spend predicts
    conversion only weakly (measured reduction <1%), which is itself the
    lesson — CUPED removes only the variance the covariate explains. The visit
    outcome, where history is more informative, demonstrates the same machinery
    with a covariate that actually carries signal.
    """
    y = df[outcome].to_numpy(dtype=float)
    x = df[cfg.cuped_covariate].to_numpy(dtype=float)
    treatment = df["treatment"].to_numpy(dtype=int)
    theta = cuped_theta(y, x)
    y_adj = cuped_adjust(y, x, theta, float(x.mean()))
    ate_naive, se_naive = effect_and_se(y, treatment)
    ate_adj, se_adj = effect_and_se(y_adj, treatment)
    return {
        "theta": theta,
        "variance_reduction": variance_reduction(y, y_adj),
        "ate_naive": ate_naive,
        "ate_se_naive": se_naive,
        "ate_cuped": ate_adj,
        "ate_se_cuped": se_adj,
        "se_reduction": 1.0 - se_adj / se_naive,
        "var_naive": float(np.var(y, ddof=1)),
        "var_adjusted": float(np.var(y_adj, ddof=1)),
    }


def cuped_read(cfg: UpliftConfig, df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """CUPED reads for the primary (conversion) and secondary (visit) outcomes."""
    return {
        "conversion": cuped_outcome_read(cfg, df, "conversion"),
        "visit": cuped_outcome_read(cfg, df, "visit"),
    }


def cuped_multivariate_outcome_read(
    cfg: UpliftConfig, df: pd.DataFrame, outcome: str
) -> dict[str, Any]:
    """CUPED with several pre-treatment covariates (adds cfg.cuped_extra_covariates).

    Additive read: the univariate ``cuped_outcome_read`` (and its ``_meta.cuped``
    metrics keys) is untouched; this sibling measures how much the extra
    covariates (e.g. ``recency``) remove on top of the primary covariate.
    """
    covariates = [cfg.cuped_covariate, *cfg.cuped_extra_covariates]
    y = df[outcome].to_numpy(dtype=float)
    x = df[covariates].to_numpy(dtype=float)
    treatment = df["treatment"].to_numpy(dtype=int)
    theta = cuped_theta_multi(y, x)
    y_adj = cuped_adjust_multi(y, x, theta, x.mean(axis=0))
    ate_naive, se_naive = effect_and_se(y, treatment)
    ate_adj, se_adj = effect_and_se(y_adj, treatment)
    return {
        "covariates": covariates,
        "theta": [float(t) for t in theta],
        "variance_reduction": variance_reduction(y, y_adj),
        "ate_naive": ate_naive,
        "ate_se_naive": se_naive,
        "ate_cuped": ate_adj,
        "ate_se_cuped": se_adj,
        "se_reduction": 1.0 - se_adj / se_naive,
        "var_naive": float(np.var(y, ddof=1)),
        "var_adjusted": float(np.var(y_adj, ddof=1)),
    }


def cuped_multivariate_read(cfg: UpliftConfig, df: pd.DataFrame) -> dict[str, Any]:
    """Multivariate CUPED reads for the primary and secondary outcomes."""
    return {
        "conversion": cuped_multivariate_outcome_read(cfg, df, "conversion"),
        "visit": cuped_multivariate_outcome_read(cfg, df, "visit"),
    }


# ---------------------------------------------------------------------------
# Multi-arm read (secondary, model-estimated — see multiarm.py for conventions)
# ---------------------------------------------------------------------------


def multi_arm_read(
    cfg: UpliftConfig,
    df_multi: pd.DataFrame,
    two_arm_metrics: dict[str, dict[str, float]],
) -> tuple[dict[str, Any], dict[str, tuple[np.ndarray, np.ndarray]]]:
    """Assemble the ``multi_arm`` metrics block from the three-arm scored frame.

    Combines: the recommended-arm distribution, per-arm EMPIRICAL Qini reads on
    the randomized pairs, the MODEL-ESTIMATED policy comparison (best-arm vs
    single-arm/random/mail-everyone) with paired-bootstrap CIs, and the best-arm
    break-even send cost vs mail-everyone-mens. The committed two-arm numbers
    are embedded unchanged under each policy's ``two_arm_reference`` where
    applicable. Returns (json-serializable block, per-arm figure curves).
    """
    u_m = df_multi["uplift_mens"].to_numpy(dtype=float)
    u_w = df_multi["uplift_womens"].to_numpy(dtype=float)
    seg = df_multi["segment"].to_numpy()
    y = df_multi["conversion"].to_numpy(dtype=float)
    n_total = len(df_multi)

    recommended = recommend_arm(u_m, u_w)
    shares = arm_shares(recommended)
    est = assigned_uplift(u_m, u_w, recommended)
    curves = multi_arm_policy_curves(u_m, u_w)

    arm_reads = per_arm_qini_read(seg, y, u_m, u_w)

    boot_seed = cfg.seed + 1999  # distinct stream from the two-arm bootstrap (seed + 999)
    stats = bootstrap_multi_arm_stats(
        u_m,
        u_w,
        seg,
        y,
        budget=cfg.policy_budget,
        n_total=n_total,
        revenue_per_conversion=cfg.revenue_per_conversion,
        cost_per_email=cfg.cost_per_email,
        n_boot=cfg.bootstrap_reps,
        seed=boot_seed,
    )

    per_arm: dict[str, Any] = {}
    arm_curves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for arm, seg_name in ARMS:
        read = arm_reads[arm]
        fr, inc = read.pop("curve")
        arm_curves[arm] = (fr, inc)
        pair_mask = np.isin(seg, [seg_name, "No E-Mail"])
        score = u_m if arm == "mens" else u_w
        deciles = uplift_by_decile(
            (seg[pair_mask] == seg_name).astype(int),
            y[pair_mask],
            score[pair_mask],
            cfg.n_deciles,
        )
        per_arm[arm] = {
            **read,
            "qini_ci": list(percentile_ci(stats["arm_qini"][arm])),
            "incremental_conversions_full_ci": list(
                percentile_ci(stats["arm_incremental_full"][arm])
            ),
            "deciles": {k: [float(v) for v in arr] for k, arr in deciles.items()},
        }
    per_arm["binary_t_learner"] = {
        "qini_coefficient": two_arm_metrics["t_learner"]["qini_coefficient"],
        "incremental_conversions_full": two_arm_metrics["t_learner"][
            "incremental_conversions_full"
        ],
        "note": "committed two-arm Mens-vs-control T-learner read (empirical, unchanged)",
    }

    random_budget_point = float(
        cfg.policy_budget * est.sum() * cfg.revenue_per_conversion
        - cfg.policy_budget * n_total * cfg.cost_per_email
    )
    policies: dict[str, Any] = {}
    for policy in MULTI_ARM_POLICIES:
        fr, inc = curves[policy]
        profit_full = float(inc[-1] * cfg.revenue_per_conversion - n_total * cfg.cost_per_email)
        if policy in ("best_arm", "single_arm"):
            # Curving policies: read the curve at the grid point nearest the budget.
            k = int(np.argmin(np.abs(fr - cfg.policy_budget)))
            inc_budget = float(inc[k])
            mailed_budget = float(fr[k]) * n_total
            qini = estimated_qini_coefficient(est if policy == "best_arm" else u_m)
        else:
            # Straight-line policies: profit is linear in the mailed fraction, so
            # the budget point is exact (a 2-point curve would land on f=0).
            inc_budget = cfg.policy_budget * float(inc[-1])
            mailed_budget = cfg.policy_budget * n_total
            qini = 0.0  # on the random line by construction
        profit_budget = float(
            inc_budget * cfg.revenue_per_conversion - mailed_budget * cfg.cost_per_email
        )
        entry: dict[str, Any] = {
            "qini_coefficient": qini,
            "incremental_conversions_full": float(inc[-1]),
            "profit_full": profit_full,
            "profit_at_budget": profit_budget,
            "profit_random_at_budget": random_budget_point,
            "profit_delta_vs_random": profit_budget - random_budget_point,
            "profit_at_budget_ci": list(percentile_ci(stats["profit_at_budget"][policy])),
            "model_estimated": True,
        }
        if policy in ("best_arm", "single_arm"):
            entry["qini_ci"] = list(percentile_ci(stats["qini"][policy]))
        policies[policy] = entry
    # The committed two-arm numbers ride along, unchanged, for continuity.
    policies["single_arm"]["two_arm_reference"] = dict(two_arm_metrics["t_learner"])
    policies["single_arm"]["two_arm_reference"]["policy"] = "t_learner"
    policies["random"]["two_arm_reference"] = dict(two_arm_metrics["random"])

    pairs: dict[str, Any] = {}
    for other in ("single_arm", "random", "mail_everyone_mens", "mail_everyone_womens"):
        diff = stats["profit_at_budget"]["best_arm"] - stats["profit_at_budget"][other]
        ci = percentile_ci(diff)
        pairs[f"best_arm - {other}"] = {
            "profit_at_budget_diff_ci": list(ci),
            "spans_zero": ci_spans_zero(ci),
        }
    qini_diff = stats["qini"]["best_arm"] - stats["qini"]["single_arm"]
    qini_ci = percentile_ci(qini_diff)
    pairs["best_arm - single_arm_qini"] = {
        "qini_diff_ci": list(qini_ci),
        "qini_diff_spans_zero": ci_spans_zero(qini_ci),
    }

    # Best-arm break-even vs mail-everyone-mens at the policy budget (the
    # model-estimated mirror of the two-arm formula):
    #   c* = revenue * (inc_mens(1) - inc_best(budget)) / (N * (1 - budget))
    fr_b, inc_b = curves["best_arm"]
    k_b = int(np.argmin(np.abs(fr_b - cfg.policy_budget)))
    inc_budget = float(inc_b[k_b])
    inc_mens_full = float(u_m.sum())
    n_mail_budget = n_total * (1.0 - cfg.policy_budget)
    breakeven = cfg.revenue_per_conversion * (inc_mens_full - inc_budget) / n_mail_budget

    seg_names, seg_n = np.unique(seg, return_counts=True)
    seg_counts = {name: int(count) for name, count in zip(seg_names, seg_n, strict=True)}
    block: dict[str, Any] = {
        "frame": {
            "n_rows": n_total,
            "n_mens": seg_counts.get("Mens E-Mail", 0),
            "n_womens": seg_counts.get("Womens E-Mail", 0),
            "n_control": seg_counts.get("No E-Mail", 0),
        },
        "recommended_arm_shares": shares,
        "estimated_incremental_conversions_full_send": {
            "all": float(est.sum()),
            "mens": float(u_m.sum()),
            "womens": float(u_w.sum()),
        },
        "per_arm": per_arm,
        "policies": policies,
        "ci": {
            "method": "paired row bootstrap of per-arm uplift scores, percentile interval; "
            "policy-level reads are model-estimated, arm-level reads empirical",
            "n_boot": cfg.bootstrap_reps,
            "seed": boot_seed,
            "pairs": pairs,
        },
        "best_arm_break_even": {
            "vs": "mail_everyone_mens",
            "cost_per_email": float(breakeven),
            "policy_budget": cfg.policy_budget,
            "formula": "c* = revenue * (inc_mens(1) - inc_best(budget)) / (N * (1 - budget)); "
            "incremental conversions are model-estimated (summed predicted uplift)",
        },
        "note": "Multi-arm read is MODEL-ESTIMATED at the policy level: incremental "
        "conversions are summed predicted uplift over the targeted set, not observed "
        "counterfactuals. Only the per-arm Qini/A-B contrasts on the randomized "
        "arm-vs-control pairs are empirical causal reads.",
    }
    return block, arm_curves


def power_analysis(cfg: UpliftConfig, df: pd.DataFrame) -> dict[str, float]:
    """Analytic required sample size for the measured conversion effect."""
    treatment = df["treatment"].to_numpy(dtype=int)
    outcome = df["conversion"].to_numpy(dtype=float)
    n_t = int(treatment.sum())
    n_c = len(treatment) - n_t
    p_t = float(outcome[treatment == 1].mean())
    p_c = float(outcome[treatment == 0].mean())
    read = power_read(p_t, p_c, cfg.alpha, cfg.power, actual_per_arm=min(n_t, n_c))
    return read.model_dump()


def decile_table(cfg: UpliftConfig, df: pd.DataFrame, policy: str) -> dict[str, list[float]]:
    """Predicted vs empirical uplift per decile for the chosen policy."""
    table = uplift_by_decile(
        df["treatment"].to_numpy(dtype=int),
        df["conversion"].to_numpy(dtype=float),
        df[policy].to_numpy(dtype=float),
        cfg.n_deciles,
    )
    return {k: [float(v) for v in arr] for k, arr in table.items()}


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def qini_figure(
    curves: dict[str, tuple[np.ndarray, np.ndarray]],
    best: str,
    bands: dict[str, tuple[np.ndarray, np.ndarray]] | None = None,
    band_grid: np.ndarray | None = None,
) -> go.Figure:
    """Qini curves: model policies promoted, random/treat-everyone demoted grey.

    ``bands`` carries per-policy 95% bootstrap ribbons (interpolated onto
    ``band_grid``); added after styling so the grey/demote pass skips them.
    Each policy gets an explicit, hue-separated color — the colorway's
    teal/sky are indistinguishable on overlapping curves — and the ribbons
    stay deliberately faint so the lines read through them.
    """
    fig = go.Figure()
    for policy, (fr, inc) in curves.items():
        fig.add_scatter(
            x=fr,
            y=inc,
            mode="lines",
            name=policy,
            line={"width": 3.5 if policy == best else 2.0},
        )
    apply_theme(fig)
    style_runs(fig, best=best)
    # Rotate/darken policy colors so response / T / X-learner + the two
    # non-model references are separable at a glance (audit: overlapping
    # bands/curves). Unknown policies keep the colorway.
    policy_style = {
        "response": {"color": "#2dd4bf"},
        "t_learner": {"color": "#fbbf24"},
        "x_learner": {"color": "#f472b6"},
        "random": {"color": "#64748b", "dash": "dash"},
        "treat-everyone": {"color": "#94a3b8", "dash": "dot"},
    }
    for trace in fig.data:
        style = policy_style.get(str(getattr(trace, "name", "") or ""))
        if style is not None:
            trace.update(line=style)
    if bands and band_grid is not None:
        for policy, (lo, hi) in bands.items():
            fig.add_scatter(
                x=band_grid,
                y=hi,
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
            fig.add_scatter(
                x=band_grid,
                y=lo,
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(45, 212, 191, 0.08)",
                line={"width": 0},
                name=f"{policy} 95% band",
                hoverinfo="skip",
            )
    fig.update_layout(
        title="Qini curves by targeted fraction",
        xaxis_title="fraction of customers targeted (top scores first)",
        yaxis_title="incremental conversions",
    )
    add_takeaway(
        fig,
        "incremental conversions, policies + random/treat-everyone refs — 95% bootstrap bands",
    )
    return fig


def decile_figure(table: dict[str, list[float]], policy: str) -> go.Figure:
    """Predicted vs empirical uplift per decile (the calibration check for uplift)."""
    fig = go.Figure()
    fig.add_bar(x=table["decile"], y=table["mean_score"], name=f"{policy} mean predicted uplift")
    fig.add_bar(x=table["decile"], y=table["empirical_uplift"], name="empirical uplift")
    apply_theme(fig)
    style_runs(fig)
    fig.update_layout(
        title="Predicted vs empirical uplift by decile",
        xaxis_title="decile (1 = highest predicted uplift)",
        yaxis_title="uplift (conversion-rate difference)",
        barmode="group",
    )
    add_takeaway(
        fig,
        f"mean predicted score vs empirical treated-control contrast per decile ({policy})",
    )
    return fig


def profit_figure(
    cfg: UpliftConfig,
    curves: dict[str, tuple[np.ndarray, np.ndarray]],
    n_total: int,
) -> go.Figure:
    """Incremental profit vs budget fraction for every policy."""
    fig = go.Figure()
    for policy, (fr, inc) in curves.items():
        profit = profit_curve(fr, inc, n_total, cfg.revenue_per_conversion, cfg.cost_per_email)
        fig.add_scatter(
            x=fr,
            y=profit,
            mode="lines",
            name=policy,
            line={"width": 3.5 if policy == "t_learner" else 2.0},
        )
    fig.add_hline(y=0.0, line_dash="dot", line_color="#64748b", name="no campaign")
    apply_theme(fig)
    style_runs(fig, best="t_learner")
    # The recommended operating point is whichever policy maximizes profit at
    # the configured budget — mark it prominently (audit: the 25% recommendation
    # was not visible on the frontier).
    budget_profits = {
        policy: float(
            profit_curve(
                np.array([cfg.policy_budget]),
                np.array([float(np.interp(cfg.policy_budget, fr, inc))]),
                n_total,
                cfg.revenue_per_conversion,
                cfg.cost_per_email,
            )[0]
        )
        for policy, (fr, inc) in curves.items()
    }
    # The recommendation is among the ranking policies only: random and
    # treat-everyone are reference curves, not budgetable targeting strategies
    # (treat-everyone realizes full incremental conversions at any fraction,
    # so it would otherwise always "win" the max).
    candidates = {
        policy: profit
        for policy, profit in budget_profits.items()
        if not is_baseline_run(policy) and policy != "treat-everyone"
    }
    recommended = max(candidates, key=lambda policy: candidates[policy])
    recommended_profit = budget_profits[recommended]
    fig.add_scatter(
        x=[cfg.policy_budget],
        y=[recommended_profit],
        mode="markers",
        name=f"recommended top-{cfg.policy_budget:.0%} ({recommended})",
        marker={
            "symbol": "star",
            "size": 18,
            "color": "#fbbf24",
            "line": {"width": 1.5, "color": "#0f172a"},
        },
    )
    fig.add_annotation(
        x=cfg.policy_budget,
        y=recommended_profit,
        text=(
            f"recommended top-{cfg.policy_budget:.0%} budget<br>"
            f"${recommended_profit:,.0f} ({recommended})"
        ),
        showarrow=True,
        arrowhead=2,
        ax=-10,
        ay=55,
        font={"size": 13, "color": "#fbbf24"},
    )
    fig.update_layout(
        title="Incremental profit vs budget fraction",
        xaxis_title="budget fraction (share of customers emailed)",
        yaxis_title=f"profit (revenue {cfg.revenue_per_conversion:.0f} USD/conversion, "
        f"{cfg.cost_per_email:.2f} USD/email)",
    )
    add_takeaway(
        fig,
        "star = recommended policy at the 25% budget; dotted line = no campaign",
    )
    return fig


def cuped_figure(reads: dict[str, dict[str, float]]) -> go.Figure:
    """Before/after panel: outcome variance with and without CUPED adjustment."""
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Conversion (primary)", "Visit (secondary)"),
    )
    for col, (outcome, read) in enumerate(reads.items(), start=1):
        fig.add_bar(
            x=["naive", "CUPED"],
            y=[read["var_naive"], read["var_adjusted"]],
            name=outcome,
            row=1,
            col=col,
        )
        fig.update_yaxes(title_text="var(Y)", row=1, col=col)
    apply_theme(fig, width=1000, height=480)
    fig.update_layout(title="Outcome variance: naive vs CUPED-adjusted")
    add_takeaway(
        fig,
        "var(Y) before vs after CUPED, per outcome; covariate = log1p prior spend (pre-treatment)",
    )
    return fig


# ---------------------------------------------------------------------------
# Multi-arm figures (model-estimated frontier + empirical per-arm Qini)
# ---------------------------------------------------------------------------


def qini_per_arm_figure(
    arm_curves: dict[str, tuple[np.ndarray, np.ndarray]],
    binary_curve: tuple[np.ndarray, np.ndarray],
) -> go.Figure:
    """Empirical Qini curves per arm on the randomized pairs (+ committed binary read)."""
    fig = go.Figure()
    arm_style = {"mens": {"color": "#fbbf24"}, "womens": {"color": "#f472b6"}}
    for arm in ("mens", "womens"):
        fr, inc = arm_curves[arm]
        fig.add_scatter(x=fr, y=inc, mode="lines", name=f"uplift_{arm}")
    fr_b, inc_b = binary_curve
    fig.add_scatter(
        x=fr_b,
        y=inc_b,
        mode="lines",
        name="binary t_learner (two-arm, committed)",
        line={"color": "#2dd4bf", "dash": "dash"},
    )
    apply_theme(fig)
    style_runs(fig)
    for trace in fig.data:
        style = arm_style.get(str(getattr(trace, "name", "") or "").replace("uplift_", ""))
        if style is not None:
            trace.update(line=style)
    fig.update_layout(
        title="Per-arm Qini curves (randomized arm vs control pairs)",
        xaxis_title="fraction of pair rows targeted (top scores first)",
        yaxis_title="incremental conversions (empirical arm contrast)",
    )
    add_takeaway(
        fig,
        "each arm scored by its own cross-fitted T-learner; dashed = committed two-arm T-learner",
    )
    return fig


def profit_frontier_multi_arm_figure(
    cfg: UpliftConfig,
    curves: dict[str, tuple[np.ndarray, np.ndarray]],
    n_total: int,
) -> go.Figure:
    """MODEL-ESTIMATED profit frontier: best-arm vs the single-arm/mail-everyone strategies."""
    fig = go.Figure()
    for policy, (fr, inc) in curves.items():
        profit = profit_curve(fr, inc, n_total, cfg.revenue_per_conversion, cfg.cost_per_email)
        fig.add_scatter(
            x=fr,
            y=profit,
            mode="lines",
            name=policy,
            line={"width": 3.5 if policy == "best_arm" else 2.0},
        )
    fig.add_hline(y=0.0, line_dash="dot", line_color="#64748b", name="no campaign")
    apply_theme(fig)
    style_runs(fig, best="best_arm")
    # Mark the best-arm operating point at the configured budget.
    fr_b, inc_b = curves["best_arm"]
    k = int(np.argmin(np.abs(fr_b - cfg.policy_budget)))
    point = float(
        profit_curve(
            np.array([fr_b[k]]),
            np.array([inc_b[k]]),
            n_total,
            cfg.revenue_per_conversion,
            cfg.cost_per_email,
        )[0]
    )
    fig.add_scatter(
        x=[fr_b[k]],
        y=[point],
        mode="markers",
        name=f"best-arm @ {cfg.policy_budget:.0%}",
        marker={
            "symbol": "star",
            "size": 18,
            "color": "#fbbf24",
            "line": {"width": 1.5, "color": "#0f172a"},
        },
    )
    fig.update_layout(
        title="Multi-arm profit frontier (model-estimated incremental conversions)",
        xaxis_title="budget fraction (share of customers emailed)",
        yaxis_title=f"profit (revenue {cfg.revenue_per_conversion:.0f} USD/conversion, "
        f"{cfg.cost_per_email:.2f} USD/email)",
    )
    add_takeaway(
        fig,
        "star = best-arm policy at the configured budget; incremental conversions are "
        "summed predicted uplift (model-estimated, not counterfactual)",
    )
    return fig


def recommended_arm_figure(shares: dict[str, float]) -> go.Figure:
    """Distribution of the per-customer recommended arm (shares sum to 1)."""
    labels = ["mens", "womens", "none"]
    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=[shares[label] for label in labels],
        marker_color=["#fbbf24", "#f472b6", "#64748b"],
        text=[f"{shares[label]:.1%}" for label in labels],
        textposition="outside",
    )
    apply_theme(fig)
    style_runs(fig)
    fig.update_layout(
        title="Recommended arm per customer (argmax of per-arm uplift vs no send)",
        xaxis_title="recommended arm",
        yaxis_title="share of customers",
    )
    add_takeaway(
        fig,
        "argmax(uplift_mens, uplift_womens, 0); ties and non-positive scores -> none",
    )
    return fig


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _money_signed(x: float) -> str:
    return f"\u2212${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def _ci_str(ci: list[float]) -> str:
    return f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def _add_multi_arm_section(
    report: EvalReport, cfg: UpliftConfig, multi_arm: dict[str, Any]
) -> None:
    """Report the multi-arm read: policy ladder, per-arm Qini, arm shares, verdict."""
    ma_rows = [
        f"| policy | Qini [95% CI] | profit @ {cfg.policy_budget * 100:.0f}% budget "
        "[95% CI] | Δ vs random |",
        "|---|---|---|---|",
    ]
    for policy in MULTI_ARM_POLICIES:
        m = multi_arm["policies"][policy]
        qini_ci_s = _ci_str(m["qini_ci"]) if "qini_ci" in m else "—"
        ma_rows.append(
            f"| {policy} | {m['qini_coefficient']:.2f} {qini_ci_s} "
            f"| {_money(m['profit_at_budget'])} {_ci_str(m['profit_at_budget_ci'])} "
            f"| {_money(m['profit_delta_vs_random'])} |"
        )
    report.add_markdown_table("Multi-arm policy ladder (model-estimated)", "\n".join(ma_rows))
    # Per-arm empirical Qini on the randomized pairs (the causal arm-level read).
    pa_rows = [
        "| arm | n (arm + control) | Qini [95% CI] | incremental conv. @ full send [95% CI] |",
        "|---|---|---|---|",
    ]
    for arm in ("mens", "womens"):
        read = multi_arm["per_arm"][arm]
        pa_rows.append(
            f"| {arm} | {read['n_arm']:,} + {read['n_control']:,} "
            f"| {read['qini_coefficient']:.2f} {_ci_str(read['qini_ci'])} "
            f"| {read['incremental_conversions_full']:.1f} "
            f"{_ci_str(read['incremental_conversions_full_ci'])} |"
        )
    binary = multi_arm["per_arm"]["binary_t_learner"]
    pa_rows.append(
        f"| binary t_learner (two-arm, committed) | — | {binary['qini_coefficient']:.2f} "
        f"| {binary['incremental_conversions_full']:.1f} |"
    )
    report.add_markdown_table("Per-arm Qini (randomized pairs)", "\n".join(pa_rows))

    shares = multi_arm["recommended_arm_shares"]
    share_rows = [
        "| recommended arm | share |",
        "|---|---|",
        f"| Mens E-Mail | {shares['mens']:.1%} |",
        f"| Womens E-Mail | {shares['womens']:.1%} |",
        f"| none (both scores ≤ 0 or tied) | {shares['none']:.1%} |",
    ]
    report.add_markdown_table("Recommended-arm distribution", "\n".join(share_rows))

    pair_lines = []
    for name, pair in multi_arm["ci"]["pairs"].items():
        if "profit_at_budget_diff_ci" in pair:
            lo, hi = pair["profit_at_budget_diff_ci"]
            note = "spans zero" if pair["spans_zero"] else "excludes zero"
            pair_lines.append(f"<li>{name}: [{_money_signed(lo)}, {_money_signed(hi)}] {note}</li>")
    q_pair = multi_arm["ci"]["pairs"].get("best_arm - single_arm_qini")
    qini_line = ""
    if q_pair is not None:
        q_lo, q_hi = q_pair["qini_diff_ci"]
        verdict = (
            "spans zero — not established" if q_pair["qini_diff_spans_zero"] else "excludes zero"
        )
        qini_line = (
            f" The paired Qini difference (best-arm - single-arm) is "
            f"[{q_lo:.2f}, {q_hi:.2f}] and {verdict}."
        )
    ba = multi_arm["policies"]["best_arm"]
    be = multi_arm["best_arm_break_even"]
    report.add_html(
        "Multi-arm read, honestly stated",
        "<p>This block upgrades the experiment to a multi-treatment read: each arm "
        "is scored against the shared control with a cross-fitted T-learner, and a "
        "<b>best-arm policy</b> recommends the arm with the highest estimated uplift "
        "per customer (no send when both scores are ≤ 0 or tied). Because no "
        "randomized assignment realizes the recommended arm mix, every policy-level "
        "number here is <b>model-estimated</b> — incremental conversions are the "
        "summed predicted uplift over the targeted set, not observed counterfactuals. "
        "Only the per-arm Qini/A-B contrasts above are empirical causal reads. Two "
        "caveats travel with every figure: predicted magnitudes run hot (the decile "
        "check shows ~2x inflation, and the full-base sums include deployment-style "
        "scores for the other arm's customers), so the dollar LEVELS are optimistic "
        "planning numbers — use them to RANK policies, not to forecast revenue; and "
        "the bootstrap resamples rows, not models, so the intervals are "
        "within-model precision (the two-arm ranking verdict shows how wide Qini "
        "gets across refits).</p>"
        f"<p>At the {cfg.policy_budget:.0%} budget the best-arm policy earns "
        f"<b>{_money(ba['profit_at_budget'])}</b> (model-estimated) vs "
        f"{_money(multi_arm['policies']['single_arm']['profit_at_budget'])} for "
        "single-arm Mens targeting and "
        f"{_money(multi_arm['policies']['mail_everyone_mens']['profit_full'])} for "
        "mailing everyone the Mens email. Paired-bootstrap differences (best-arm "
        "minus comparator, n=1000, seeded):</p><ul>" + "".join(pair_lines) + "</ul>"
        f"<p>Break-even vs mail-everyone-mens: the best-arm policy overtakes full "
        f"mailing above ≈<b>${be['cost_per_email']:.2f}</b> per email "
        f"({be['formula']}).{qini_line} The committed two-arm numbers are unchanged "
        "and remain the primary read; this block is the new per-customer "
        "channel-choice capability.</p>",
    )


def build_report(
    cfg: UpliftConfig,
    policy_metrics: dict[str, dict[str, float]],
    cuped: dict[str, dict[str, float]],
    power: dict[str, float],
    deciles: dict[str, list[float]],
    best: str,
    ci: dict[str, Any] | None = None,
    cost_sens: dict[str, Any] | None = None,
    cuped_multi: dict[str, dict[str, Any]] | None = None,
    multi_arm: dict[str, Any] | None = None,
) -> EvalReport:
    """Assemble the HTML report: experiment read, CUPED, power, policy ladder."""
    report = EvalReport(title="Retention Uplift & Experimentation — evaluation")

    n_arm = int(power["actual_per_arm"])
    experiment_rows = [
        "| read | value |",
        "|---|---|",
        f"| treated / control | {n_arm:,} / {n_arm:,} |",
        f"| conversion rate, treated | {power['p_treated']:.4f} |",
        f"| conversion rate, control | {power['p_control']:.4f} |",
        f"| ATE (difference in means) | {cuped['conversion']['ate_naive']:+.5f} |",
        f"| ATE standard error (naive) | {cuped['conversion']['ate_se_naive']:.5f} |",
    ]
    report.add_markdown_table("Experiment read (conversion)", "\n".join(experiment_rows))

    cuped_rows = [
        "| outcome | ATE (naive -> CUPED) | SE (naive -> CUPED) | variance reduction |",
        "|---|---|---|---|",
    ]
    for outcome in ("conversion", "visit"):
        read = cuped[outcome]
        cuped_rows.append(
            f"| {outcome} | {read['ate_naive']:+.5f} -> {read['ate_cuped']:+.5f} "
            f"| {read['ate_se_naive']:.5f} -> {read['ate_se_cuped']:.5f} "
            f"| {read['variance_reduction'] * 100:.2f}% |"
        )
    report.add_markdown_table(
        f"CUPED (covariate: {cfg.cuped_covariate} = log1p prior-year spend)",
        "\n".join(cuped_rows),
    )
    conv = cuped["conversion"]
    visit = cuped["visit"]
    report.add_html(
        "CUPED verdict",
        "<p>The adjustment is unbiased by construction — both ATEs are essentially "
        "identical and only the variance moves. On conversion it removes "
        f"<b>{conv['variance_reduction'] * 100:.2f}%</b> of variance: prior-year spend "
        "barely predicts a ~1% event. On visit, where history is informative, the same "
        f"machinery removes <b>{visit['variance_reduction'] * 100:.1f}%</b>. CUPED is "
        "exactly as good as its covariate — covariate selection is the design decision, "
        "not the formula.</p>",
    )
    if cuped_multi is not None:
        m_conv = cuped_multi["conversion"]
        m_visit = cuped_multi["visit"]
        report.add_html(
            "CUPED, second covariate",
            "<p>Adding <b>recency</b> alongside log_history (multivariate CUPED, additive "
            "read under <code>_meta.cuped_multivariate</code>): conversion variance "
            f"reduction moves from {conv['variance_reduction'] * 100:.2f}% to "
            f"<b>{m_conv['variance_reduction'] * 100:.2f}%</b>, visit from "
            f"{visit['variance_reduction'] * 100:.2f}% to "
            f"<b>{m_visit['variance_reduction'] * 100:.2f}%</b> — recency adds almost "
            "nothing here either. The univariate read above is unchanged; the demo "
            "carries both so covariate selection stays measurable, not assumed.</p>",
        )

    power_rows = [
        "| quantity | value |",
        "|---|---|",
        f"| measured effect | {power['effect']:+.5f} |",
        f"| alpha / power | {cfg.alpha} / {cfg.power} |",
        f"| required n per arm | {power['n_per_arm']:,} |",
        f"| required n total | {power['n_total']:,} |",
        f"| available per arm | {power['actual_per_arm']:,} |",
        f"| sufficient? | {'yes' if power['sufficient'] else 'no'} |",
    ]
    report.add_markdown_table("Power analysis (two-sided two-proportion)", "\n".join(power_rows))

    ladder = [
        f"| policy | Qini [95% CI] | profit @ {cfg.policy_budget * 100:.0f}% budget [95% CI] "
        "| delta vs random |",
        "|---|---|---|---|",
    ]
    for policy in [*SCORE_POLICIES, *BASELINE_POLICIES]:
        m = policy_metrics[policy]
        delta = m["profit_delta_vs_random"]
        qini_ci_s = (
            _ci_str(ci["policies"][policy]["qini_ci"])
            if ci is not None and policy in ci["policies"]
            else "—"
        )
        profit_ci_s = (
            _ci_str(ci["policies"][policy]["profit_at_budget_ci"])
            if ci is not None and policy in ci["policies"]
            else "—"
        )
        ladder.append(
            f"| {policy} | {m['qini_coefficient']:.2f} {qini_ci_s} "
            f"| {_money(m['profit_at_budget'])} {profit_ci_s} "
            f"| {'—' if np.isnan(delta) else _money(delta)} |"
        )
    report.add_markdown_table("Policy ladder (out-of-fold)", "\n".join(ladder))

    if ci is not None:
        pair = ci["pairs"].get("response - t_learner")
        if pair is not None:
            # The difference is defined as response - t_learner throughout.
            q_lo, q_hi = pair["qini_diff_ci"]
            p_lo, p_hi = pair["profit_at_budget_diff_ci"]
            if pair["qini_diff_spans_zero"]:
                qini_verdict = (
                    f"the 95% CI on the Qini difference (response - T-learner) "
                    f"[{q_lo:.2f}, {q_hi:.2f}] spans zero — the curve-area ranking is "
                    "<b>not established</b>"
                )
            else:
                sign = "above" if q_lo > 0 else "below"
                qini_verdict = (
                    f"the 95% CI on the Qini difference (response - T-learner) "
                    f"[{q_lo:.2f}, {q_hi:.2f}] sits {sign} zero"
                )
            if pair["profit_at_budget_diff_spans_zero"]:
                profit_verdict = f"the profit difference CI [{p_lo:,.0f}, {p_hi:,.0f}] spans zero"
            else:
                profit_verdict = (
                    f"the profit difference CI [{p_lo:,.0f}, {p_hi:,.0f}] excludes zero — "
                    "T-learner's budget-profit advantage is established (the individual "
                    "profit CIs overlap; the paired difference is the honest read)"
                )
            report.add_html(
                "Model ranking, with intervals",
                f"<p>The response model's Qini area is nominally higher, but {qini_verdict}; "
                f"at the 25% budget, {profit_verdict}. The recommendation stands on the "
                "money, and the curve-area ranking is stated with its interval rather "
                "than asserted.</p>",
            )

        baseline_lines: list[str] = []
        vs_random = ci.get("t_learner_vs_random")
        if vs_random is not None:
            r_lo, r_hi = vs_random["profit_at_budget_diff_ci"]
            r_note = (
                "spans zero"
                if vs_random["spans_zero"]
                else "excludes zero — the advantage is established"
            )
            baseline_lines.append(
                f"<li>vs <b>random</b> targeting at the {cfg.policy_budget:.0%} budget: "
                f"paired profit difference CI [{_money_signed(r_lo)}, {_money_signed(r_hi)}] "
                f"{r_note} (point {_money_signed(vs_random['point_diff'])})</li>"
            )
        vs_mail = ci.get("t_learner_vs_mail_everyone")
        if vs_mail is not None:
            m_lo, m_hi = vs_mail["profit_at_budget_diff_ci"]
            m_note = (
                "spans zero"
                if vs_mail["spans_zero"]
                else "sits entirely below zero — at this send cost mail-everyone's raw "
                "profit is the established winner"
            )
            baseline_lines.append(
                f"<li>vs <b>mail-everyone</b> at ${cfg.cost_per_email:.2f}/email: "
                f"paired profit difference CI [{_money_signed(m_lo)}, {_money_signed(m_hi)}] "
                f"{m_note} (point {_money_signed(vs_mail['point_diff'])})</li>"
            )
        if baseline_lines:
            report.add_html(
                "T-learner vs baselines, with intervals",
                "<p>The same paired bootstrap anchors the recommended policy against the "
                "two non-model baselines (T-learner minus comparator):</p><ul>"
                + "".join(baseline_lines)
                + "</ul>",
            )

    if cost_sens is not None:
        rows = [
            "| cost/email | best fraction | profit (best) | profit (mail everyone) | top-k wins? |",
            "|---|---|---|---|---|",
        ]
        for r in cost_sens["rows"]:
            rows.append(
                f"| ${r['cost_per_email']:.3f} | {r['profit_max_fraction']:.0%} "
                f"| {_money(r['profit_at_max'])} | {_money(r['profit_mail_everyone'])} "
                f"| {'yes' if r['targeting_beats_mail_everyone'] else 'no'} |"
            )
        report.add_markdown_table(f"Cost sensitivity ({cost_sens['best_policy']})", "\n".join(rows))
        report.add_html(
            "Cost sensitivity verdict",
            f"<p>Mail-everyone is the profit maximum at the current ${cfg.cost_per_email:.2f} "
            f"per email. The top-{cost_sens['policy_budget']:.0%} policy overtakes it once "
            f"sends cost more than <b>${cost_sens['breakeven_cost_per_email']:.2f}</b> each "
            "— the fatigue / list-wear regime — because every marginal email below the cut "
            "costs more than the conversions it recovers.</p>",
        )

    if multi_arm is not None:
        _add_multi_arm_section(report, cfg, multi_arm)

    top_share = cfg.policy_budget
    report.add_html(
        "Recommended policy",
        f"<p>Target the top {top_share:.0%} of customers by <b>{best}</b> score. "
        f"Expected incremental profit vs random targeting at that budget: "
        f"<b>{_money(policy_metrics[best]['profit_delta_vs_random'])}</b> per campaign wave "
        f"over {len(deciles['decile'])} deciles scored out-of-fold.</p>"
        "<p>Predicting churn or conversion is not changing it — see Project 05's fairness "
        "finding for the same lesson on the retention side: a response model ranks likely "
        "buyers; only an uplift read separates persuadables from sure things and from "
        "customers the campaign actively annoys.</p>",
    )
    return report


def evaluate_core(cfg: UpliftConfig) -> Path:
    """Full evaluation: reads, figures, metrics.json, report.html."""
    scores_path = cfg.data_dir / "scores.parquet"
    if not scores_path.exists():
        raise FileNotFoundError(
            f"{scores_path} missing — run `uv run python -m uplift_experimentation.cli train` first"
        )
    scores_multi_path = cfg.data_dir / "scores_multi.parquet"
    if not scores_multi_path.exists():
        raise FileNotFoundError(
            f"{scores_multi_path} missing — run the train stage first "
            "(uv run python -m uplift_experimentation.cli train)"
        )
    df = pd.read_parquet(scores_path)
    df_multi = pd.read_parquet(scores_multi_path)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = cfg.reports_dir / "figures"

    policy_metrics, curves = evaluate_policies(cfg, df)
    cuped = cuped_read(cfg, df)
    cuped_multi = cuped_multivariate_read(cfg, df)
    power = power_analysis(cfg, df)
    best = max(SCORE_POLICIES, key=lambda p: policy_metrics[p]["profit_delta_vs_random"])
    deciles = decile_table(cfg, df, best)
    ci_meta, bands, band_grid = bootstrap_ci_read(cfg, df)
    cost_sens = cost_sensitivity_read(cfg, curves, best, len(df))
    multi_arm, arm_curves = multi_arm_read(cfg, df_multi, policy_metrics)
    curves_multi = multi_arm_policy_curves(
        df_multi["uplift_mens"].to_numpy(dtype=float),
        df_multi["uplift_womens"].to_numpy(dtype=float),
    )

    figures = {
        "qini_curves": qini_figure(curves, best, bands, band_grid),
        "uplift_by_decile": decile_figure(deciles, best),
        "profit_frontier": profit_figure(cfg, curves, len(df)),
        "cuped_variance": cuped_figure(cuped),
        "cost_sensitivity": cost_sensitivity_figure(cost_sens, cfg),
        "qini_per_arm": qini_per_arm_figure(arm_curves, curves["t_learner"]),
        "profit_frontier_multi_arm": profit_frontier_multi_arm_figure(
            cfg, curves_multi, len(df_multi)
        ),
        "recommended_arm_distribution": recommended_arm_figure(multi_arm["recommended_arm_shares"]),
    }
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")

    report = build_report(
        cfg, policy_metrics, cuped, power, deciles, best, ci_meta, cost_sens, cuped_multi, multi_arm
    )
    first_plotly = True
    for name in figures:
        # the standalone .html stays on disk for the API figure route; the
        # report itself embeds the div so committed reports self-contain
        report.add_figure(
            name.replace("_", " ").title(), figures[name], include_plotlyjs=first_plotly
        )
        first_plotly = False
    report.write(cfg.reports_dir / "report.html")

    metrics: dict[str, Any] = {policy: dict(vals) for policy, vals in policy_metrics.items()}
    metrics["multi_arm"] = multi_arm
    metrics["_meta"] = {
        "best_policy": best,
        "cuped": cuped,
        "cuped_multivariate": cuped_multi,
        "power": power,
        "ci": ci_meta,
        "cost_sensitivity": cost_sens,
        "cost_model": {
            "revenue_per_conversion": cfg.revenue_per_conversion,
            "cost_per_email": cfg.cost_per_email,
        },
        "deciles": deciles,
    }
    (cfg.reports_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    log.info(
        "evaluate: best=%s qini=%.4f profit@%.0f%%=%.0f (random %.0f) | CUPED var "
        "reduction %.1f%% | power sufficient=%s | multi-arm best-arm profit@%.0f%%=%.0f",
        best,
        policy_metrics[best]["qini_coefficient"],
        cfg.policy_budget * 100,
        policy_metrics[best]["profit_at_budget"],
        policy_metrics[best]["profit_random_at_budget"],
        cuped["conversion"]["variance_reduction"] * 100,
        power["sufficient"],
        cfg.policy_budget * 100,
        multi_arm["policies"]["best_arm"]["profit_at_budget"],
    )
    return cfg.reports_dir / "report.html"
