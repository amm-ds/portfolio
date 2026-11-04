"""report.html + results.md assembly over the committed artifacts.

Rebuilds offline from ``reports/metrics.json`` + the figure JSON payloads +
the story's mermaid diagrams (the same pattern as project 11), so the report
stage is pure assembly: no retraining, no re-scoring.
"""

import json
from pathlib import Path
from typing import Any

from portfolio_eval.report import EvalReport, figures_from_json, mermaid_blocks_from_story

REPORT_TITLE = "12 — Tabular ML & Deep Learning Lifecycle (UCI Bike Sharing, hourly)"

RUN_LABELS = {
    "seasonal_naive": "seasonal naive (floor)",
    "ridge": "ridge",
    "random_forest": "random forest",
    "lightgbm_hpo": "LightGBM (Optuna HPO)",
    "mlp": "tabular MLP (PyTorch)",
}


def _results_table(metrics: dict[str, Any]) -> str:
    lines = [
        "| candidate | test MAE | test RMSE | test MAPE % |",
        "|---|---|---|---|",
    ]
    for name, label in RUN_LABELS.items():
        if name not in metrics:
            continue
        row = metrics[name]
        lines.append(f"| {label} | {row['mae']:.1f} | {row['rmse']:.1f} | {row['mape']:.1f} |")
    return "\n".join(lines)


def _ablation_table(meta: dict[str, Any]) -> str:
    lines = [
        "| dropout | weight decay | early stopping | val MAE | test MAE |",
        "|---|---|---|---|---|",
    ]
    for row in meta.get("ablation", []):
        flag = " ✅" if row["selected"] else ""
        lines.append(
            f"| {'on' if row['dropout_on'] else 'off'} | "
            f"{'on' if row['weight_decay_on'] else 'off'} | "
            f"{'on' if row['early_stopping_on'] else 'off'} | "
            f"{row['val_mae']:.1f} | {row['test_mae']:.1f}{flag} |"
        )
    return "\n".join(lines)


def build_report(reports_dir: Path, project_dir: Path) -> Path:
    """Assemble report.html + results.md from committed metrics and figures."""
    metrics = json.loads((reports_dir / "metrics.json").read_text())
    meta = metrics.get("_meta", {})
    metadata = json.loads((reports_dir / "evaluation_metadata.json").read_text())
    figures = figures_from_json(reports_dir / "figures")
    ci = meta.get("mae_improvement_vs_floor_ci", {})

    report = EvalReport(title=REPORT_TITLE)
    report.add_html("Protocol", f"<p>{metadata['protocol']}</p>")
    report.add_markdown_table(
        "Scored-once test window — every candidate, one score", _results_table(metrics)
    )
    report.add_html(
        "Champion vs floor",
        "<p>Champion: <b>{}</b> (selected by lowest validation MAE). MAE improvement over the "
        "seasonal-naive floor: point +{:.1f} rentals, 95% paired-bootstrap CI [{:.1f}, {:.1f}] "
        "over {:,} resamples — significant_95={}.</p>".format(
            RUN_LABELS.get(meta.get("champion", ""), meta.get("champion", "?")),
            ci.get("point", float("nan")),
            ci.get("lo", float("nan")),
            ci.get("hi", float("nan")),
            ci.get("n_boot", 0),
            ci.get("significant_95"),
        ),
    )
    report.add_markdown_table("MLP regularization ablation (2x2x2)", _ablation_table(meta))
    first_plotly = True
    for name, fig in figures.items():
        report.add_figure(name.replace("_", " ").title(), fig, include_plotlyjs=first_plotly)
        first_plotly = False
    for heading, code in mermaid_blocks_from_story(project_dir).items():
        report.add_mermaid(heading, code)
    report.write(reports_dir / "report.html")

    limits = "\n".join(f"- {line}" for line in metadata.get("limits", []))
    (reports_dir / "results.md").write_text(
        f"# {REPORT_TITLE}\n\n"
        f"## Protocol\n\n{metadata['protocol']}\n\n"
        f"## Scored-once test window\n\n{_results_table(metrics)}\n\n"
        f"Champion: **{meta.get('champion')}** — MAE improvement vs floor "
        f"+{ci.get('point', float('nan')):.1f}, 95% CI [{ci.get('lo', float('nan')):.1f}, "
        f"{ci.get('hi', float('nan')):.1f}], significant_95={ci.get('significant_95')}.\n\n"
        f"## MLP regularization ablation (2x2x2)\n\n{_ablation_table(meta)}\n\n"
        f"## Limits\n\n{limits}\n\n"
        "Figures: `reports/figures/` (JSON + HTML). "
        "Full record: `reports/metrics.json`, `reports/train_runs.json`, "
        "`reports/evaluation_metadata.json`.\n"
    )
    return reports_dir / "report.html"
