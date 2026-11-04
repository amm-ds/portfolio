"""HTML + markdown report assembly over the committed artifacts.

The HTML report embeds the figures as interactive Plotly divs (the shared
:class:`portfolio_eval.report.EvalReport` builder) and the same mermaid
diagrams the case study carries; ``results.md`` mirrors the tables for the
repo reader. ``build_report`` regenerates both offline from
``metrics.json`` + the figure JSON payloads — no re-run needed.
"""

from pathlib import Path
from typing import Any

from portfolio_core.plotting import save_html, save_json
from portfolio_eval.report import EvalReport, figures_from_json, mermaid_blocks_from_story

from data_engineering.metrics import ENGINE_ORDER
from data_engineering.tasks import TASKS

REPORT_TITLE = "11 — Data Engineering: pandas vs Polars vs DuckDB"
_LABELS = {"pandas": "pandas", "polars": "Polars", "duckdb": "DuckDB"}


def _fmt_s(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}" if value < 10 else f"{value:.1f}"


def _fmt_x(value: float | None) -> str:
    return "—" if value is None else f"x{value:.1f}"


def headline_table(metrics: dict[str, Any]) -> str:
    """Task x engine median-time table with speedup columns."""
    lines = [
        "| task | pandas | Polars | DuckDB | Polars vs pandas | DuckDB vs pandas | fastest |",
        "|---|---|---|---|---|---|---|",
    ]
    for task in TASKS:
        block = metrics["tasks"].get(task.name)
        if block is None:
            continue
        engines = block["engines"]
        fastest = min(engines, key=lambda e: engines[e]["time_median_s"])
        cells = [_fmt_s(engines[e]["time_median_s"]) if e in engines else "—" for e in ENGINE_ORDER]
        speed = [
            _fmt_x(engines[e]["speedup_vs_pandas"]) if e in engines else "—"
            for e in ENGINE_ORDER[1:]
        ]
        lines.append(
            f"| {task.name} | {cells[0]} | {cells[1]} | {cells[2]} "
            f"| {speed[0]} | {speed[1]} | {_LABELS[fastest]} |"
        )
    return "\n".join(lines)


def memory_table(metrics: dict[str, Any]) -> str:
    """Task x engine peak-RSS table (fresh-process probes)."""
    lines = [
        "| task | pandas | Polars | DuckDB |",
        "|---|---|---|---|",
    ]
    for task in TASKS:
        block = metrics["tasks"].get(task.name)
        if block is None:
            continue
        engines = block["engines"]
        cells = [
            f"{engines[e]['peak_rss_mb']:.0f} MB" if engines.get(e, {}).get("peak_rss_mb") else "—"
            for e in ENGINE_ORDER
        ]
        lines.append(f"| {task.name} | {cells[0]} | {cells[1]} | {cells[2]} |")
    return "\n".join(lines)


def cold_table(metrics: dict[str, Any]) -> str:
    """Cold fresh-process read vs warm median for the IO tasks."""
    lines = [
        "| IO task | pandas cold → warm | Polars cold → warm | DuckDB cold → warm |",
        "|---|---|---|---|",
    ]
    for task in TASKS:
        block = metrics["tasks"].get(task.name)
        if block is None or block["category"] != "io":
            continue
        engines = block["engines"]
        cells = []
        for e in ENGINE_ORDER:
            eng = engines.get(e, {})
            cold, warm = eng.get("cold_s"), eng.get("time_median_s")
            cells.append(f"{_fmt_s(cold)} → {_fmt_s(warm)}" if cold is not None else "—")
        lines.append(f"| {task.name} | {cells[0]} | {cells[1]} | {cells[2]} |")
    return "\n".join(lines)


def write_figures(figures: dict[str, Any], figures_dir: Path) -> None:
    """Persist every figure as showcase JSON + docs HTML."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    for name, fig in figures.items():
        save_json(fig, figures_dir / f"{name}.json")
        save_html(fig, figures_dir / f"{name}.html")


def build_report(
    metrics: dict[str, Any],
    metadata: dict[str, Any] | None,
    figures: dict[str, Any],
    reports_dir: Path,
    *,
    project_dir: Path,
) -> Path:
    """Assemble report.html + results.md from measured metrics + figures."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = EvalReport(title=REPORT_TITLE)
    report.add_html(
        "Protocol",
        "<p>{}</p>".format(metadata["protocol_statement"] if metadata else ""),
    )
    report.add_markdown_table(
        "Headline — median wall time per task (s) + speedup vs pandas", headline_table(metrics)
    )
    report.add_markdown_table(
        "Memory — peak RSS per task (MB, fresh-process probe)", memory_table(metrics)
    )
    report.add_markdown_table(
        "IO tasks — cold fresh-process read → warm median (s)", cold_table(metrics)
    )
    first_plotly = True
    for name, fig in figures.items():
        report.add_figure(
            name.replace("_", " ").title(),
            fig,
            include_plotlyjs=first_plotly,
        )
        first_plotly = False
    for heading, code in mermaid_blocks_from_story(project_dir).items():
        report.add_mermaid(heading, code)
    report.write(reports_dir / "report.html")

    summary = metrics["summary"]["by_engine"]
    geo_lines = "\n".join(
        f"- {_LABELS[e]}: total median time {summary[e]['total_time_s']:.2f}s, "
        f"geomean speedup vs pandas x{summary[e]['geomean_speedup_vs_pandas']}"
        for e in ENGINE_ORDER
        if e in summary
    )
    (reports_dir / "results.md").write_text(
        f"# {REPORT_TITLE}\n\n"
        f"## Headline — median wall time per task (s)\n\n{headline_table(metrics)}\n\n"
        f"## Memory — peak RSS per task (MB)\n\n{memory_table(metrics)}\n\n"
        f"## IO tasks — cold → warm (s)\n\n{cold_table(metrics)}\n\n"
        f"## By engine\n\n{geo_lines}\n\n"
        f"Figures: `reports/figures/` (JSON + HTML). "
        f"Full record: `reports/metrics.json`, `reports/evaluation_metadata.json`.\n"
    )
    return reports_dir / "report.html"


def build_report_offline(reports_dir: Path, project_dir: Path) -> Path:
    """Regenerate report.html + results.md from committed artifacts (no re-run)."""
    import json

    metrics = json.loads((reports_dir / "metrics.json").read_text())
    figures = figures_from_json(reports_dir / "figures")
    return build_report(metrics, None, figures, reports_dir, project_dir=project_dir)
