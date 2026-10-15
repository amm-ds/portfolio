"""Offline report builder: figures + metrics.json + report.html from a BenchRun."""

from __future__ import annotations

import json
from pathlib import Path

from portfolio_core.plotting import save_html, save_json
from portfolio_eval.report import EvalReport

from inference_serving.config import BenchConfig
from inference_serving.figures import all_figures
from inference_serving.schemas import BenchRun, CellResult


def headline_table(cells: list[CellResult]) -> str:
    """Markdown headline table: model x engine x concurrency."""
    lines = [
        "| model | runner | c | p50 s | p95 s | p99 s | tok/s (agg) | valid | quality | failures |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in sorted(cells, key=lambda c: (c.model, c.concurrency)):
        lines.append(
            f"| {c.model} | {c.engine} | {c.concurrency} "
            f"| {_f(c.p50_latency_s)} | {_f(c.p95_latency_s)} | {_f(c.p99_latency_s)} "
            f"| {_f(c.agg_tok_per_s)} | {c.schema_valid_rate:.2f} | {c.quality_rate:.2f} "
            f"| {c.n_failures}/{c.n_requests} |"
        )
    return "\n".join(lines)


def _f(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def electricity_cost_per_mtok(
    tok_per_s: float, *, usd_per_kwh: float, system_load_watts: float
) -> float | None:
    """Amortized-electricity cost of 1M output tokens at a sustained tok/s.

    Declared assumptions (DESIGN.md): constant system draw under inference,
    flat residential kWh price. This is an honesty note, not a bill.
    """
    if tok_per_s <= 0:
        return None
    hours = 1e6 / tok_per_s / 3600.0
    return hours * (system_load_watts / 1000.0) * usd_per_kwh


def cost_table(run: BenchRun, cfg: BenchConfig) -> str:
    """Local electricity vs hypothetical cloud rate card, per 1M output tokens."""
    lines = [
        "| model | best agg tok/s | electricity $/1M out "
        f"(assumed {cfg.system_load_watts:.0f} W, ${cfg.usd_per_kwh:.2f}/kWh) "
        "| cloud-equivalent $/1M out (hypothetical rate card) |",
        "|---|---|---|---|",
    ]
    for model in sorted({c.model for c in run.cells}):
        best = max((c.agg_tok_per_s or 0.0) for c in run.cells if c.model == model)
        elec = electricity_cost_per_mtok(
            best, usd_per_kwh=cfg.usd_per_kwh, system_load_watts=cfg.system_load_watts
        )
        cloud = cfg.cloud_usd_per_mtok_output.get(model)
        lines.append(
            f"| {model} | {best:.1f} | ${elec:.4f} | "
            f"{f'${cloud:.2f}' if cloud is not None else 'n/a'} |"
        )
    return "\n".join(lines)


def build_report(run: BenchRun, cfg: BenchConfig) -> Path:
    """Write reports/report.html + metrics.json + figures from a BenchRun."""
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = cfg.reports_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    report = EvalReport(title="08-inference-serving — LLM inference & serving benchmark")
    repeats = run.cells[0].n_requests // 8 if run.cells else 0
    report.add_markdown_table(
        f"Headline table — Ollama {run.ollama_version or 'unknown'} on {run.platform}; "
        f"fixed structured-output task (8 prompts x {repeats} repeats/cell, "
        "temperature 0, bounded output tokens)",
        headline_table(run.cells),
    )
    report.add_markdown_table(
        "Cost per 1M output tokens — local electricity (measured tok/s, declared power "
        "assumptions) vs hypothetical cloud rate card",
        cost_table(run, cfg),
    )
    if run.notes:
        report.add_html(
            "Run notes (engine auto-detection, fallbacks)",
            "<ul>" + "".join(f"<li>{n}</li>" for n in run.notes) + "</ul>",
        )

    figures = all_figures(run, cfg)
    for name, fig in figures.items():
        html_path = save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")
        report.add_html(
            name.replace("_", " ").title(),
            f'<p><a href="figures/{html_path.name}">interactive figure</a> '
            f"(<code>{html_path.name}</code>)</p>",
        )

    (cfg.reports_dir / "metrics.json").write_text(
        json.dumps(
            {
                "ollama_version": run.ollama_version,
                "platform": run.platform,
                "full": run.full,
                "cells": [c.model_dump() for c in run.cells],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return report.write(cfg.reports_dir / "report.html")
