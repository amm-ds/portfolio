"""Regression tests for compact scalability presentation."""

import json
import math
from pathlib import Path

from data_engineering.figures import scalability_lines


def test_scalability_combines_slope_summary_and_groupby_detail() -> None:
    metrics = json.loads((Path(__file__).resolve().parents[1] / "reports/metrics.json").read_text())
    fig = scalability_lines(metrics)

    assert len(fig.data) == 8  # four slope series + four group-by lines
    assert fig.layout.xaxis.title.text == "log-log slope (1 = linear)"
    assert fig.layout.xaxis2.title.text == "rows"
    assert fig.layout.yaxis2.title.text == "median wall time (s)"
    assert fig.layout.yaxis2.type == "log"
    assert sum(trace.showlegend is not False for trace in fig.data) == 4


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed payloads (title-patched without a re-run) agree with traces."""
    figures = Path(__file__).resolve().parents[1] / "reports" / "figures"

    speedup = json.loads((figures / "speedup_overview.json").read_text())
    title = speedup["layout"]["title"]["text"]
    geomeans: dict[str, float] = {}
    for trace in speedup["data"]:
        if trace.get("xaxis", "x") != "x":
            continue  # right panel is vs sqlite, not the pandas baseline
        xs = trace["x"]
        geomeans[trace["name"]] = math.exp(sum(math.log(x) for x in xs) / len(xs))
    assert f"\u00d7{geomeans['Polars']:.1f}" in title
    assert f"\u00d7{geomeans['DuckDB']:.1f}" in title
    assert f"about {1 / geomeans['sqlite']:.0f}\u00d7 slower" in title

    scal = json.loads((figures / "scalability_lines.json").read_text())
    stitle = scal["layout"]["title"]["text"]
    slopes = {
        t["name"]: dict(zip(t["y"], t["x"], strict=True))
        for t in scal["data"]
        if t.get("xaxis", "x") == "x"
    }
    assert f"slopes {slopes['Polars']['groupby']:.2f}, {slopes['DuckDB']['groupby']:.2f}" in stitle
    assert all(abs(s - 1.0) < 0.05 for s in slopes["pandas"].values())

    mem = json.loads((figures / "memory_lollipop.json").read_text())
    mtitle = mem["layout"]["title"]["text"]
    peaks = {t["name"]: max(t["y"]) for t in mem["data"] if "stem" not in t["name"]}
    assert max(peaks, key=lambda e: peaks[e]) == "sqlite"
    assert f"to {peaks['sqlite']:,.0f} MB" in mtitle
