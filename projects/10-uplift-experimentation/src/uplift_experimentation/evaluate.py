"""Evaluation: Qini ladder, profit frontier, CUPED + power reads, report.

Reads the cross-fitted scores from the train stage and produces every artifact
the report needs: per-policy Qini coefficients, decile checks, profit under the
campaign cost model, the CUPED variance-reduction panel, and the analytic
power analysis — plus the four themed figures (HTML + JSON).
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json, style_runs
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
    incremental_at_full,
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

    # Baselines share the analytic random line; treat-everyone is the f=1 point.
    np.asarray(cfg.budget_fractions, dtype=float)

    def profit_at(fr: np.ndarray, inc: np.ndarray, f: float) -> float:
        idx = int(np.argmin(np.abs(fr - f)))
        return float(
            profit_curve(
                np.array([fr[idx]]),
                np.array([inc[idx]]),
                n_total,
                cfg.margin_per_conversion,
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
                cfg.margin_per_conversion,
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


def qini_figure(curves: dict[str, tuple[np.ndarray, np.ndarray]], best: str) -> go.Figure:
    """Qini curves: model policies promoted, random/treat-everyone demoted grey."""
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
    fig.update_layout(
        title="Qini curves — incremental conversions vs targeted fraction",
        xaxis_title="fraction of customers targeted (top scores first)",
        yaxis_title="incremental conversions",
        legend={"orientation": "h", "y": -0.2},
    )
    add_takeaway(
        fig,
        f"The {best} ranking concentrates incremental conversions in the top deciles; "
        "random and treat-everyone collapse onto the same diagonal.",
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
        title=f"Uplift by decile — {policy}",
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
        profit = profit_curve(fr, inc, n_total, cfg.margin_per_conversion, cfg.cost_per_email)
        fig.add_scatter(
            x=fr,
            y=profit,
            mode="lines",
            name=policy,
            line={"width": 3.5 if policy == "x_learner" else 2.0},
        )
    fig.add_hline(y=0.0, line_dash="dot", line_color="#64748b", name="no campaign")
    apply_theme(fig)
    style_runs(fig, best="x_learner")
    fig.update_layout(
        title="Profit frontier under the campaign cost model",
        xaxis_title="budget fraction (share of customers emailed)",
        yaxis_title=f"profit (margin ${cfg.margin_per_conversion:.0f}/conversion, "
        f"${cfg.cost_per_email:.2f}/email)",
        legend={"orientation": "h", "y": -0.2},
    )
    add_takeaway(
        fig,
        "Profit = incremental conversions x margin - emails x cost; a model only pays "
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


def build_report(
    cfg: UpliftConfig,
    policy_metrics: dict[str, dict[str, float]],
    cuped: dict[str, dict[str, float]],
    power: dict[str, float],
    deciles: dict[str, list[float]],
    best: str,
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
        f"| policy | Qini | profit @ {cfg.policy_budget * 100:.0f}% budget | delta vs random |",
        "|---|---|---|---|",
    ]
    for policy in [*SCORE_POLICIES, *BASELINE_POLICIES]:
        m = policy_metrics[policy]
        delta = m["profit_delta_vs_random"]
        ladder.append(
            f"| {policy} | {m['qini_coefficient']:.4f} | {_money(m['profit_at_budget'])} "
            f"| {'—' if np.isnan(delta) else _money(delta)} |"
        )
    report.add_markdown_table("Policy ladder (out-of-fold)", "\n".join(ladder))

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

    figures = {
        "qini_curves": qini_figure(curves, best),
        "uplift_by_decile": decile_figure(deciles, best),
        "profit_frontier": profit_figure(cfg, curves, len(df)),
        "cuped_variance": cuped_figure(cuped),
    }
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")

    report = build_report(cfg, policy_metrics, cuped, power, deciles, best)
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
        "cost_model": {
            "margin_per_conversion": cfg.margin_per_conversion,
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
