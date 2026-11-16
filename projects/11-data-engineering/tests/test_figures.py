"""Regression tests for compact scalability presentation."""

import json
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
