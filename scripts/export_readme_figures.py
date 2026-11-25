#!/usr/bin/env python3
"""Export static PNG snapshots of project figures for docs pages and the README.

Reads the plotly JSON artifacts each project publishes (reports/figures/*.json)
and renders PNGs into docs/assets/. Interactive figures remain the canonical
view (ADR-0005) — these statics exist so the mkdocs pages and README show
results without running anything.

Rendering goes through kaleido directly (not plotly's write_image wrapper)
so heavy figures (geo choropleths, dense scatters) get a 300 s budget instead
of kaleido's default 90 s.

Run: uv run python scripts/export_readme_figures.py
"""

from pathlib import Path

import kaleido
import plotly.io as pio

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "docs" / "assets"
OUT_README = ASSETS / "readme"
RENDER_TIMEOUT_S = 300

# README hero figures: output name → (project dir, preferred stem, fallback stem)
FIGURES: dict[str, tuple[str, str, str]] = {
    "mobility-demand-map.png": ("07-open-data-mobility", "zone_demand_map", "zone_hour_heatmap"),
    "rag-retrieval-ladder.png": ("01-rag-agent", "retrieval_ladder", "final_outcome"),
    "anomaly-timelines.png": ("03-anomaly-detection", "nab_timelines", "nab_alert_budget"),
}

# Per-project figures embedded in the mkdocs case-study pages
# (docs/projects/<id>.md): project dir → figure stems, in page order.
# Stems listed here must actually be embedded in the page; unreferenced PNGs
# are pruned (see collaboration/reviews/20261124-orchestrator-review 5.4/2.3).
DOCS_FIGURES: dict[str, tuple[str, ...]] = {
    "01-rag-agent": (
        "retrieval_ladder",
        "final_outcome",
        "failure_taxonomy",
        "verify_funnel",
        "chunk_size_sweep",
    ),
    "03-anomaly-detection": ("nab_timelines",),
    "04-nlp-classification": ("confusion_matrix_selected", "training_curve"),
    "05-ml-pipeline-churn": ("business_cost_curve", "bootstrap_ci"),
    "06-routing-optimization": ("route_map_C101", "family_gap"),
    "07-open-data-mobility": ("zone_demand_map", "gbm_vs_nn", "weather_elasticity"),
    "08-inference-serving": ("latency_concurrency", "engine_panel"),
    "09-agentic-workflows": (
        "suite_summary",
        "tool_usage_matrix",
        "node_waterfall",
    ),
    "10-uplift-experimentation": ("qini_curves", "profit_frontier", "cost_sensitivity"),
    "12-tabular-ml-lifecycle": ("model_comparison", "bootstrap_ci"),
    "13-model-serving": ("latency_concurrency_lines", "footprint_cost_bars"),
    "15-dynamic-pricing-rl": (
        "profit_vs_baselines",
        "price_traces",
        "bound_share_by_rho",
        "calibration_overview",
    ),
}

WIDTH = 1200
HEIGHT = 700
SCALE = 2


def render_png(src: Path, dest: Path) -> None:
    fig = pio.read_json(str(src))
    png = kaleido.calc_fig_sync(
        fig,
        opts={"format": "png", "width": WIDTH, "height": HEIGHT, "scale": SCALE},
        kopts={"timeout": RENDER_TIMEOUT_S},
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(png)


def main() -> None:
    for out_name, (project, stem, fallback) in FIGURES.items():
        src = REPO / "projects" / project / "reports" / "figures" / f"{stem}.json"
        if not src.exists():
            src = REPO / "projects" / project / "reports" / "figures" / f"{fallback}.json"
        if not src.exists():
            print(f"SKIP {out_name} — neither stem found (run the project's pipeline)")
            continue
        render_png(src, OUT_README / out_name)
        print(f"wrote {OUT_README / out_name}")

    for project, stems in DOCS_FIGURES.items():
        out_dir = ASSETS / "projects" / project
        for stem in stems:
            # Stems containing "/" are project-relative paths (e.g. the UCI
            # track's figures live under reports_uci/figures/).
            if "/" in stem:
                src = REPO / "projects" / project / f"{stem}.json"
            else:
                src = REPO / "projects" / project / "reports" / "figures" / f"{stem}.json"
            if not src.exists():
                print(f"SKIP {project}/{stem} — artifact missing (run the project's pipeline)")
                continue
            dest = out_dir / f"{Path(stem).name}.png"
            render_png(src, dest)
            print(f"wrote {dest}")


if __name__ == "__main__":
    main()
