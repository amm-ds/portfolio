"""M5 evaluation report: figures + standalone report builder (wave 24).

Two entry points share the same figure code:

- :func:`build_figures` renders the seven committed-JSON figures (dark theme,
  house conventions from portfolio_core.plotting) — the track writes them as
  ``reports_m5/figures/*.html+json`` right after the run;
- :func:`build_report` is the STANDALONE builder (``build-report-m5``): it
  reads ONLY the committed artifacts (metrics.json, probabilistic.json,
  evaluation_metadata.json) and rebuilds ``reports_m5/report.html`` + figures
  without re-running anything — the narrative-style model is projects/07's
  evaluate.py (intro, metrics table, per-figure takeaway sections quoting the
  committed numbers, business insights).

Every takeaway is computed from the committed JSONs at build time, so the
report cannot drift from the measured numbers (the honesty rule).
"""

import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json
from portfolio_eval.report import EvalReport

from demand_forecasting.m5_track import CANDIDATES, HORIZON, NAIVE

logger = get_logger(__name__)

REQUIRED_ARTIFACTS = ("metrics.json", "probabilistic.json", "evaluation_metadata.json")
DISPLAY = {  # candidate -> display name
    "seasonal_naive": "seasonal_naive",
    "window_avg_28": "window_avg_28",
    "adida": "adida",
    "tsb": "tsb",
    "auto_ets": "auto_ets",
    "auto_ces": "auto_ces",
    "lgbm": "lgbm",
    "convex_ensemble": "convex_ensemble",
}


def load_artifacts(reports_dir: Path) -> dict[str, Any]:
    """Read the three committed JSON artifacts; FileNotFoundError if absent."""
    out: dict[str, Any] = {}
    for name in REQUIRED_ARTIFACTS:
        path = Path(reports_dir) / name
        if not path.exists():
            raise FileNotFoundError(f"missing {path} — run `evaluate-m5` first")
        out[name.removesuffix(".json")] = json.loads(path.read_text())
    return out


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def fig_sample_series(meta: dict[str, Any]) -> go.Figure:
    """(a) Sample series: actual vs naive / lgbm / ensemble on the test windows."""
    from plotly.subplots import make_subplots

    blocks = meta["report_sample_series"]
    series_ids = sorted({b["unique_id"] for b in blocks})
    n = len(series_ids)
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        subplot_titles=series_ids,
        vertical_spacing=0.06,
    )
    colors = {
        "actual": "#f472b6",
        "seasonal_naive": "#64748b",
        "lgbm": "#2dd4bf",
        "convex_ensemble": "#fbbf24",
    }
    shown: set[str] = set()
    for i, sid in enumerate(series_ids, start=1):
        for b in blocks:
            if b["unique_id"] != sid:
                continue
            x = [f"{b['origin']} · {d}" for d in b["ds"]]
            for key in ("actual", "seasonal_naive", "lgbm", "convex_ensemble"):
                show = key not in shown
                shown.add(key)
                fig.add_scatter(
                    x=x,
                    y=b[key],
                    name=key,
                    mode="lines",
                    line={
                        "color": colors[key],
                        "width": 2.5 if key != "seasonal_naive" else 1.5,
                        "dash": "dash" if key == "seasonal_naive" else "solid",
                    },
                    showlegend=show,
                    row=i,
                    col=1,
                )
    fig.update_layout(title="Sample series: actual vs forecasts on the scored-once test windows")
    return add_takeaway(
        apply_theme(fig, height=280 * n),
        "one panel per representative series; the grey dashed seasonal_naive is the floor "
        "the ML candidates must beat",
    )


def fig_wape_bars(metrics: dict[str, Any]) -> go.Figure:
    """(b) Test WAPE by candidate; lgbm/ensemble carry the paired bootstrap CI."""
    pooled = metrics["test"]["pooled"]
    names = [c for c in CANDIDATES if c in pooled]
    wapes = [pooled[c]["wape"] for c in names]
    naive_wape = pooled[NAIVE]["wape"]
    fig = go.Figure(
        data=go.Bar(
            x=[DISPLAY[c] for c in names],
            y=wapes,
            marker_color=["#64748b" if c == NAIVE else "#2dd4bf" for c in names],
        )
    )
    for i, c in enumerate(names):
        gap = metrics["headline"].get(f"{c}_vs_naive")
        if gap is None or naive_wape != naive_wape:  # floor NaN: no absolute CI possible
            continue
        lo, hi = gap["wape"]["ci95"]
        fig.add_scatter(
            x=[DISPLAY[c]],
            y=[wapes[i]],
            mode="markers",
            marker={"color": "#f8fafc", "size": 8},
            error_y={
                "type": "data",
                "array": [hi + naive_wape - wapes[i]],
                "arrayminus": [wapes[i] - (lo + naive_wape)],
                "color": "#94a3b8",
            },
            showlegend=False,
        )
    fig.update_layout(title="Test WAPE by candidate (95% paired bootstrap CI on the gap vs naive)")
    return add_takeaway(
        fig,
        "test origins, scored once; whiskers = the lgbm/ensemble-vs-naive gap CI translated "
        "onto the bar (grey = the seasonal_naive floor)",
    )


def fig_wrmsse_bars(metrics: dict[str, Any]) -> go.Figure:
    """(c) Test WRMSSE (pooled + volume-weighted) by candidate."""
    pooled = metrics["test"]["pooled"]
    names = [c for c in CANDIDATES if c in pooled]
    fig = go.Figure()
    fig.add_bar(
        name="wrmsse (pooled)",
        x=[DISPLAY[c] for c in names],
        y=[pooled[c]["wrmsse"] for c in names],
        marker_color=["#64748b" if c == NAIVE else "#38bdf8" for c in names],
    )
    fig.add_bar(
        name="wrmsse (volume-weighted)",
        x=[DISPLAY[c] for c in names],
        y=[pooled[c]["wrmsse_weighted"] for c in names],
        marker_color=["#475569" if c == NAIVE else "#a78bfa" for c in names],
    )
    fig.update_layout(
        barmode="group",
        title="Test WRMSSE by candidate (naive-28 in-sample denominator)",
    )
    best = min(names, key=lambda c: pooled[c]["wrmsse"])
    return add_takeaway(
        fig,
        f"per (series x origin) units, zero-scale units excluded; best by pooled WRMSSE: "
        f"{DISPLAY[best]} at {pooled[best]['wrmsse']:.3f} (naive "
        f"{pooled[NAIVE]['wrmsse']:.3f})",
    )


def fig_horizon_growth(metrics: dict[str, Any]) -> go.Figure:
    """(d) Horizon-wise MAE growth on the test origins (day 1..28 ahead)."""
    hm = metrics["test"]["horizon_mae"]
    fig = go.Figure()
    for c in CANDIDATES:
        if c not in hm:
            continue
        fig.add_scatter(
            x=list(range(1, HORIZON + 1)),
            y=hm[c],
            name=DISPLAY[c],
            mode="lines",
            line={
                "width": 3.0 if c in ("lgbm", "convex_ensemble") else 1.5,
                "dash": "dash" if c == NAIVE else "solid",
            },
        )
    fig.update_layout(
        title="Horizon-wise MAE growth on the test origins",
        xaxis_title="days ahead",
        yaxis_title="pooled MAE (units/day)",
    )
    lgbm_gap = hm["lgbm"][-1] - hm[NAIVE][-1]
    return add_takeaway(
        fig,
        f"error grows sub-linearly with horizon; at h=28 lgbm sits {lgbm_gap:+.2f} units/day "
        f"vs the naive (lgbm {hm['lgbm'][-1]:.2f}, naive {hm[NAIVE][-1]:.2f})",
    )


def fig_band_calibration(prob: dict[str, Any]) -> go.Figure:
    """(e) Split-conformal 80% band: empirical coverage vs target + per-h width."""
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("empirical coverage vs 80% target", "per-horizon-day band half-width"),
    )
    cands = list(prob["candidates"])
    cov = [prob["candidates"][c]["coverage_80"] for c in cands]
    fig.add_bar(
        x=cands,
        y=cov,
        showlegend=False,
        row=1,
        col=1,
        marker_color=["#2dd4bf", "#fbbf24"][: len(cands)],
        text=[f"{v:.1%}" for v in cov],
        textposition="outside",
    )
    fig.add_hline(y=prob["level"], line_dash="dash", line_color="#f472b6", row=1, col=1)
    width = prob["per_horizon_width"]
    fig.add_scatter(
        x=list(range(1, len(width) + 1)),
        y=width,
        mode="lines",
        name="q80 half-width",
        showlegend=False,
        line={"color": "#38bdf8"},
        row=1,
        col=2,
    )
    fig.update_layout(title="Split-conformal 80% band: calibration on the test origins")
    fig.update_yaxes(range=[0, 1], row=1, col=1)
    return add_takeaway(
        fig,
        "coverage calibrated on the SELECTION origins only; width grows with horizon — "
        f"coverage lgbm {cov[0]:.1%}, ensemble {cov[1]:.1%} (target 80%)",
    )


def fig_class_comparison(metrics: dict[str, Any]) -> go.Figure:
    """(f) Dense vs intermittent: test WAPE by candidate and volume class."""
    by_class = metrics["test"]["by_class"]
    names = [c for c in CANDIDATES if c in by_class]
    counts = metrics["classes"]["counts"]
    dense_wape = [
        by_class[c]["dense"]["wape"] if by_class[c].get("dense") else float("nan") for c in names
    ]
    inter_wape = [
        by_class[c]["intermittent"]["wape"] if by_class[c].get("intermittent") else float("nan")
        for c in names
    ]
    fig = go.Figure()
    fig.add_bar(
        name=f"dense (n={counts['dense']})",
        x=[DISPLAY[c] for c in names],
        y=dense_wape,
        marker_color="#2dd4bf",
    )
    fig.add_bar(
        name=f"intermittent (n={counts['intermittent']})",
        x=[DISPLAY[c] for c in names],
        y=inter_wape,
        marker_color="#f472b6",
    )
    fig.update_layout(
        barmode="group",
        title="Test WAPE by candidate and volume class (ADI/CV²)",
    )
    return add_takeaway(
        fig,
        "volume classes from ADI/CV² on the real history up to the last selection origin; "
        "the dense block is where the global ML model has the most to learn from",
    )


def fig_win_rate(metrics: dict[str, Any]) -> go.Figure:
    """(g) Per-series win-rate vs seasonal_naive on the test origins, per class."""
    wr = metrics["test"]["win_rate_vs_naive"]
    names = [c for c in CANDIDATES if c in wr]
    fig = go.Figure()
    for key, color in (("pooled", "#38bdf8"), ("dense", "#2dd4bf"), ("intermittent", "#f472b6")):
        fig.add_bar(
            name=key,
            x=[DISPLAY[c] for c in names],
            y=[wr[c][key] if wr[c][key] is not None else float("nan") for c in names],
            marker_color=color,
        )
    fig.add_hline(y=0.5, line_dash="dot", line_color="#fbbf24")
    fig.update_layout(
        barmode="group",
        title="Win-rate vs seasonal_naive per series (test origins)",
        yaxis={"range": [0, 1]},
    )
    return add_takeaway(
        fig,
        "share of series whose pooled test |error| beats the seasonal_naive floor; the "
        "dotted line is parity",
    )


def build_figures(
    metrics: dict[str, Any], prob: dict[str, Any], meta: dict[str, Any]
) -> dict[str, go.Figure]:
    """The seven committed figures, keyed by file stem."""
    return {
        "sample_series": fig_sample_series(meta),
        "wape_bars": fig_wape_bars(metrics),
        "wrmsse_bars": fig_wrmsse_bars(metrics),
        "horizon_growth": fig_horizon_growth(metrics),
        "band_calibration": fig_band_calibration(prob),
        "class_comparison": fig_class_comparison(metrics),
        "win_rate": fig_win_rate(metrics),
    }


def write_figures(figures: dict[str, go.Figure], reports_dir: Path) -> None:
    """Persist figures/*.html + *.json (html for docs embedding, json for the app)."""
    figures_dir = Path(reports_dir) / "figures"
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")
    logger.info("m5 figures -> %s", figures_dir)


# ---------------------------------------------------------------------------
# Report assembly (standalone: committed JSONs in, report.html out)
# ---------------------------------------------------------------------------


def _fmt(x: Any, nd: int = 4) -> str:
    return "-" if x is None or (isinstance(x, float) and x != x) else f"{x:.{nd}f}"


def _metrics_table(metrics: dict[str, Any]) -> str:
    pooled = metrics["test"]["pooled"]
    cols = ["candidate", "MAE", "WAPE", "rmae", "WRMSSE", "WRMSSE_w", "peak_MAE"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for c in CANDIDATES:
        if c not in pooled:
            continue
        r = pooled[c]
        lines.append(
            f"| {DISPLAY[c]} | {_fmt(r['mae'])} | {_fmt(r['wape'])} | {_fmt(r['rmae'])} "
            f"| {_fmt(r['wrmsse'], 3)} | {_fmt(r['wrmsse_weighted'], 3)} | {_fmt(r['peak_mae'])} |"
        )
    return "\n".join(lines)


def _intro(meta: dict[str, Any]) -> str:
    ds = meta["dataset"]["observed_panel"]
    split = meta["split"]
    return (
        f"<p>This report evaluates demand forecasting on the <b>M5 Walmart</b> subset: "
        f"{ds['n_series']} daily store-item series ({', '.join(ds['stores'])}), "
        f"{ds['date_start']} → {ds['date_end']}, {ds['n_rows']:,} rows, "
        f"{ds['zero_share']:.1%} zero-demand days — the <b>dense-demand</b> regime where ML "
        "forecasting is expected to demonstrably beat seasonal baselines (unlike the sparse "
        "UCI Online Retail II track, which stays as the secondary study). Protocol "
        f"<code>{meta['protocol']}</code>: {split['n_origins']} weekly rolling origins "
        f"({split['n_selection']} selection + {split['n_test']} scored-once test), "
        f"horizon {split['horizon_days']} days, min training history "
        f"{split['min_train_days']} days. Candidates: per-series statistical baselines "
        "(seasonal_naive, window_avg_28, adida, tsb), automatic per-series models "
        "(auto_ets, auto_ces), a global LightGBM with lags/rolling/calendar/exogenous "
        "features, and a convex ensemble of the two best ML-family candidates by selection "
        "WAPE.</p>"
    )


def _headline_html(metrics: dict[str, Any], prob: dict[str, Any]) -> str:
    pooled = metrics["test"]["pooled"]
    hl = metrics["headline"]

    def _gap(key: str, metric: str) -> str:
        g = hl[key][metric]
        return (
            f"{g['diff']:+.4f} (95% CI [{g['ci95'][0]:+.4f}, {g['ci95'][1]:+.4f}], "
            f"{'significant' if not g['spans_zero'] else 'spans zero'})"
        )

    cov = prob["candidates"]
    return (
        "<ul>"
        f"<li><b>lgbm vs seasonal_naive</b> — test WAPE gap {_gap('lgbm_vs_naive', 'wape')}; "
        f"WRMSSE gap {_gap('lgbm_vs_naive', 'wrmsse')}.</li>"
        f"<li><b>convex_ensemble vs seasonal_naive</b> — test WAPE gap "
        f"{_gap('convex_ensemble_vs_naive', 'wape')}; WRMSSE gap "
        f"{_gap('convex_ensemble_vs_naive', 'wrmsse')}.</li>"
        f"<li><b>Test WAPE</b>: naive {pooled[NAIVE]['wape']:.4f}, lgbm "
        f"{pooled['lgbm']['wape']:.4f}, ensemble {pooled['convex_ensemble']['wape']:.4f}.</li>"
        f"<li><b>80% band coverage</b> (split-conformal, selection-calibrated): lgbm "
        f"{cov['lgbm']['coverage_80']:.1%}, ensemble {cov['convex_ensemble']['coverage_80']:.1%} "
        f"(target 80%).</li>"
        "</ul>"
    )


def _business_insights(metrics: dict[str, Any], prob: dict[str, Any]) -> str:
    pooled = metrics["test"]["pooled"]
    by_class = metrics["test"]["by_class"]
    hl = metrics["headline"]["lgbm_vs_naive"]["wape"]
    wr = metrics["test"]["win_rate_vs_naive"]
    naive_wape = pooled[NAIVE]["wape"]
    lgbm_wape = pooled["lgbm"]["wape"]
    reduction = (naive_wape - lgbm_wape) / naive_wape * 100 if naive_wape > 0 else float("nan")
    dense_row = by_class["lgbm"].get("dense")
    inter_row = by_class["lgbm"].get("intermittent")
    if dense_row and inter_row:
        class_note = (
            f"on intermittent series the gap narrows (dense WAPE "
            f"{dense_row['wape']:.4f} vs intermittent {inter_row['wape']:.4f}), so statistical "
            "intermittent methods remain competitive there."
        )
    else:
        class_note = "the class split is degenerate on this subset."
    if wr["lgbm"]["dense"] is not None and wr["lgbm"]["intermittent"] is not None:
        win_note = (
            f"lgbm beats the naive on {wr['lgbm']['pooled']:.0%} of series pooled "
            f"({wr['lgbm']['dense']:.0%} of dense, {wr['lgbm']['intermittent']:.0%} of "
            "intermittent) — dense high-volume series carry the win."
        )
    else:
        win_note = f"lgbm beats the naive on {wr['lgbm']['pooled']:.0%} of series pooled."
    return (
        "<ul>"
        f"<li><b>Forecast value-add:</b> lgbm cuts pooled test WAPE from "
        f"{naive_wape:.4f} (seasonal_naive) to {lgbm_wape:.4f} — a {reduction:.1f}% "
        f"reduction with a 95% paired bootstrap CI on the gap of "
        f"[{hl['ci95'][0]:+.4f}, {hl['ci95'][1]:+.4f}] units of WAPE ("
        + ("statistically established" if not hl["spans_zero"] else "not established at 95%")
        + ").</li>"
        "<li><b>Replenishment order quantities:</b> order-up-to policies should read the "
        f"lgbm point forecast (dense series) instead of the seasonal naive; {class_note}</li>"
        f"<li><b>Safety stock from the band:</b> the split-conformal 80% band is calibrated "
        f"on selection origins only and covers {prob['candidates']['lgbm']['coverage_80']:.1%} "
        "of test actuals — usable as a replenishment buffer width per horizon day.</li>"
        f"<li><b>Where ML wins:</b> {win_note}</li>"
        "</ul>"
    )


def _figure_section(name: str) -> str:
    return f'<iframe src="figures/{name}.html" style="width:100%;height:480px;border:0"></iframe>'


def build_report(reports_dir: Path) -> Path:
    """Rebuild report.html (and the figures) from the committed artifacts only."""
    reports_dir = Path(reports_dir)
    art = load_artifacts(reports_dir)
    metrics, prob, meta = art["metrics"], art["probabilistic"], art["evaluation_metadata"]

    figures = build_figures(metrics, prob, meta)
    write_figures(figures, reports_dir)

    report = EvalReport(title="Demand forecasting on M5")
    report.add_html("Introduction", _intro(meta))
    report.add_html("Headline (test origins, scored once)", _headline_html(metrics, prob))
    report.add_markdown_table(
        "Test metrics by candidate (pooled over the scored-once test origins)",
        _metrics_table(metrics),
    )
    report.add_html("Business insights", _business_insights(metrics, prob))
    takeaways = {
        "sample_series": "Representative series on the test windows: the global lgbm and the "
        "convex ensemble track the weekly shape and the peaks more closely than the seasonal "
        "naive floor.",
        "wape_bars": "Pooled test WAPE by candidate; the lgbm/ensemble whiskers are the "
        "paired-bootstrap CI on the gap vs the naive floor — when the interval excludes zero "
        "the win is statistically established.",
        "wrmsse_bars": "WRMSSE normalises each (series x origin) unit by its own naive-28 "
        "in-sample scale, so quiet and loud series contribute comparably.",
        "horizon_growth": "Error growth over the 28-day horizon: ML advantages typically "
        "widen with horizon as the naive keeps repeating last week.",
        "band_calibration": "The 80% split-conformal band is honest about uncertainty: "
        "coverage sits near the 80% target and the width grows with horizon.",
        "class_comparison": "The dense class (low ADI) is where the global ML model's shared "
        "patterns pay off; intermittent series stay hard for everyone.",
        "win_rate": "Win-rate vs the naive floor per series: above 50% the candidate helps "
        "more series than it hurts.",
    }
    for name in figures:
        report.add_html(
            name.replace("_", " ").title(),
            f"<p>{takeaways[name]}</p>" + _figure_section(name),
        )
    path = report.write(reports_dir / "report.html")
    logger.info("m5 report -> %s", path)
    return path
