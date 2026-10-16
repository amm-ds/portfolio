#!/usr/bin/env python3
"""Export static PNG snapshots of flagship figures for the README.

Reads the plotly JSON artifacts each project publishes (reports/figures/*.json)
and renders PNGs into docs/assets/readme/. Interactive figures remain the
canonical view (ADR-0005) — these statics exist so the README shows results
without running anything.

Run: uv run python scripts/export_readme_figures.py
"""

from pathlib import Path

import plotly.io as pio

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "assets" / "readme"

FIGURES: dict[str, tuple[str, str, str]] = {
    # output name: (project, preferred stem, fallback stem)
    "mobility-demand-map.png": ("07-open-data-mobility", "zone_demand_map", "zone_hour_heatmap"),
    "rag-quality-cost-frontier.png": ("01-rag-agent", "retrieval_hpo_frontier", "chunk_size_sweep"),
    "routing-solver-pareto.png": ("06-routing-optimization", "pareto_gap_runtime", "route_map_C101"),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for out_name, (project, stem, fallback) in FIGURES.items():
        src = REPO / "projects" / project / "reports" / "figures" / f"{stem}.json"
        if not src.exists():
            src = REPO / "projects" / project / "reports" / "figures" / f"{fallback}.json"
        if not src.exists():
            print(f"SKIP {out_name} — neither stem found (run the project's pipeline)")
            continue
        fig = pio.read_json(str(src))
        fig.write_image(str(OUT / out_name), width=1200, height=700, scale=2)
        print(f"wrote {OUT / out_name}")


if __name__ == "__main__":
    main()
