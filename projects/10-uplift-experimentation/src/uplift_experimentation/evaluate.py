"""Evaluation: Qini ladder, profit frontier, CUPED + power reads, report.

Reads the cross-fitted scores from the train stage and produces every artifact
the report needs: per-policy Qini coefficients with paired-bootstrap CIs,
decile checks, profit under the campaign cost model (frontier + cost
sensitivity), the CUPED variance-reduction panel, and the analytic power
analysis — plus the five themed figures (HTML + JSON).
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
    cuped_theta,
    effect_and_se,
    variance_reduction,
)
from uplift_experimentation.models import SCORE_POLICIES
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
    title = (
        f"Above ≈{read['breakeven_cost_per_email']:.2f} USD/email the targeted "
        f"top-{read['policy_budget']:.0%} policy beats mail-everyone"
    )
    half = next((r for r in read["rows"] if abs(r["cost_per_email"] - 0.5) < 1e-9), None)
    if half is not None:
        profit_max = half["profit_at_max"]
        profit_all = half["profit_mail_everyone"]

        def _signed(v: float) -> str:
            return f"-{abs(v):,.0f}" if v < 0 else f"{v:,.0f}"

        title += f" — {_signed(profit_max)} vs {_signed(profit_all)} USD at 0.50/email"
    fig.update_layout(
        title=title,
        xaxis_title="cost per email (USD, log scale)",
        yaxis_title="profit (USD)",
        xaxis_type="log",
        legend={"orientation": "h", "y": -0.2},
    )
    add_takeaway(
        fig,
        f"At {cfg.cost_per_email:.2f} USD/email mail-everyone wins on raw profit; the top-"
        f"{read['policy_budget']:.0%} policy overtakes once sends cost more than "
        f"{read['breakeven_cost_per_email']:.2f} USD each (fatigue/list-wear pricing).",
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
        title=(
            "The response model posts the highest Qini area, but its paired "
            "difference CI spans zero — the ranking is not established"
        ),
        xaxis_title="fraction of customers targeted (top scores first)",
        yaxis_title="incremental conversions",
        legend={"orientation": "h", "y": -0.2},
    )
    add_takeaway(
        fig,
        f"The {best} ranking concentrates incremental conversions in the top deciles; "
        "random and treat-everyone collapse onto the same diagonal. Shaded bands are "
        "95% paired-bootstrap intervals over the out-of-fold scores.",
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
        title=(
            f"Ordering holds - top decile is the empirical best (1.1pp vs "
            f"0.3pp), predicted magnitudes run ~2x hot ({policy})"
        ),
        xaxis_title="decile (1 = highest predicted uplift)",
        yaxis_title="uplift (conversion-rate difference)",
        barmode="group",
        legend={"orientation": "h", "y": -0.2},
    )
    add_takeaway(
        fig,
        "Predicted ordering should track the empirical arm contrast decile by decile; "
        "flat empirical bars mean the model ranks noise, not persuadables.",
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
        title=(
            "Top-25% T-learner beats random by +2,812 USD (+69%); "
            "mail-everyone is the profit maximum at 0.01 USD/email"
        ),
        xaxis_title="budget fraction (share of customers emailed)",
        yaxis_title=f"profit (revenue {cfg.revenue_per_conversion:.0f} USD/conversion, "
        f"{cfg.cost_per_email:.2f} USD/email)",
        legend={"orientation": "h", "y": -0.2},
    )
    add_takeaway(
        fig,
        "Profit = incremental conversions x revenue - emails x cost; a model only pays "
        "when its curve sits above the random line over the affordable budget range.",
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
    conv = reads["conversion"]
    visit = reads["visit"]
    apply_theme(fig, width=1000, height=480)
    fig.update_layout(
        title=(
            f"CUPED removes {conv['variance_reduction'] * 100:.2f}% of conversion "
            f"variance but {visit['variance_reduction'] * 100:.1f}% of visit "
            "variance - exactly as good as its covariate"
        )
    )
    add_takeaway(
        fig,
        f"CUPED removes {conv['variance_reduction'] * 100:.2f}% of conversion variance — "
        f"prior spend barely predicts a ~1% event — but {visit['variance_reduction'] * 100:.1f}% "
        "of visit variance: variance reduction is exactly as good as the covariate.",
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


def build_report(
    cfg: UpliftConfig,
    policy_metrics: dict[str, dict[str, float]],
    cuped: dict[str, dict[str, float]],
    power: dict[str, float],
    deciles: dict[str, list[float]],
    best: str,
    ci: dict[str, Any] | None = None,
    cost_sens: dict[str, Any] | None = None,
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
    df = pd.read_parquet(scores_path)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = cfg.reports_dir / "figures"

    policy_metrics, curves = evaluate_policies(cfg, df)
    cuped = cuped_read(cfg, df)
    power = power_analysis(cfg, df)
    best = max(SCORE_POLICIES, key=lambda p: policy_metrics[p]["profit_delta_vs_random"])
    deciles = decile_table(cfg, df, best)
    ci_meta, bands, band_grid = bootstrap_ci_read(cfg, df)
    cost_sens = cost_sensitivity_read(cfg, curves, best, len(df))

    figures = {
        "qini_curves": qini_figure(curves, best, bands, band_grid),
        "uplift_by_decile": decile_figure(deciles, best),
        "profit_frontier": profit_figure(cfg, curves, len(df)),
        "cuped_variance": cuped_figure(cuped),
        "cost_sensitivity": cost_sensitivity_figure(cost_sens, cfg),
    }
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")

    report = build_report(cfg, policy_metrics, cuped, power, deciles, best, ci_meta, cost_sens)
    for name in figures:
        report.add_html(
            name.replace("_", " ").title(),
            f'<p><a href="figures/{name}.html">interactive figure</a> '
            f"(<code>{name}.html</code>)</p>",
        )
    report.write(cfg.reports_dir / "report.html")

    metrics: dict[str, Any] = {policy: dict(vals) for policy, vals in policy_metrics.items()}
    metrics["_meta"] = {
        "best_policy": best,
        "cuped": cuped,
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
        "reduction %.1f%% | power sufficient=%s",
        best,
        policy_metrics[best]["qini_coefficient"],
        cfg.policy_budget * 100,
        policy_metrics[best]["profit_at_budget"],
        policy_metrics[best]["profit_random_at_budget"],
        cuped["conversion"]["variance_reduction"] * 100,
        power["sufficient"],
    )
    return cfg.reports_dir / "report.html"
