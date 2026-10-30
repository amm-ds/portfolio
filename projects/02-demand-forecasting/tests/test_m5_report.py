"""The M5 evaluation report rebuilds offline from committed artifacts only.

Covers the embed path: figures must land in report.html as interactive Plotly
divs (self-contained report), never as relative links to gitignored sibling
files.
"""

import json
import shutil
from pathlib import Path

import pytest
from demand_forecasting.m5_report import FIGURE_CAPTIONS, REPORT_FIGURES, build_report

COMMITTED = Path(__file__).resolve().parents[1] / "reports_m5"


@pytest.mark.skipif(
    not (COMMITTED / "metrics.json").exists(),
    reason="committed M5 artifacts not present (fresh clone without DVC pull)",
)
def test_build_report_embeds_interactive_figures(tmp_path: Path) -> None:
    for name in ("metrics.json", "probabilistic.json", "evaluation_metadata.json"):
        shutil.copy(COMMITTED / name, tmp_path / name)

    metrics_before = (tmp_path / "metrics.json").read_text(encoding="utf-8")
    out = build_report(tmp_path)
    html = out.read_text(encoding="utf-8")

    # every REPORT_FIGURES figure is embedded as an interactive div
    assert html.count('class="plotly-graph-div"') == len(REPORT_FIGURES)
    # the CDN bundle is included exactly once
    assert html.count("cdn.plot.ly") == 1
    # no dead relative links to gitignored sibling .html files
    assert 'href="figures/' not in html
    # captions travel with the figures
    for name in REPORT_FIGURES:
        assert FIGURE_CAPTIONS[name] in html
    # figures are written next to the report for the API figure route
    assert (tmp_path / "figures" / f"{REPORT_FIGURES[0]}.html").exists()
    assert (tmp_path / "figures" / f"{REPORT_FIGURES[0]}.json").exists()
    # the rebuild never touches the committed numbers
    assert (tmp_path / "metrics.json").read_text(encoding="utf-8") == metrics_before
    # report.html is valid standalone HTML with the metrics table rendered
    assert "<table>" in html and "convex_ensemble" in html
    json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
