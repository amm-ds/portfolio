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

FIGURES: dict[str, tuple[str, str]] = {
    # output name: (project, figure stem)
    "mobility-demand-heatmap.png": ("07-open-data-mobility", "zone_hour_heatmap"),
    "rag-quality-cost-frontier.png": ("01-rag-agent", "retrieval_hpo_frontier"),
    "routing-c101-route-map.png": ("06-routing-optimization", "route_map_C101"),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for out_name, (project, stem) in FIGURES.items():
        src = REPO / "projects" / project / "reports" / "figures" / f"{stem}.json"
        if not src.exists():
            print(f"SKIP {out_name} — {src} not found (run the project's pipeline)")
            continue
        fig = pio.read_json(str(src))
        fig.write_image(str(OUT / out_name), width=1200, height=700, scale=2)
        print(f"wrote {OUT / out_name}")


if __name__ == "__main__":
    main()
