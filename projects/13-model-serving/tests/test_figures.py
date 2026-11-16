"""Regression tests for serving-figure bands, axes, and units."""

import json
from pathlib import Path

from model_serving.figures import (
    batch_throughput_curve,
    footprint_cost_bars,
    latency_concurrency_lines,
)


def _metrics() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / "reports/metrics.json").read_text())


def test_latency_bands_pair_each_p95_max_with_its_min() -> None:
    fig = latency_concurrency_lines(_metrics())

    for offset in (3, 8):
        high, low = fig.data[offset : offset + 2]
        assert high.name == "p95 repeat max"
        assert low.name == "p95 repeat min"
        assert low.fill == "tonexty"
        assert all(hi >= lo for hi, lo in zip(high.y, low.y, strict=True))


def test_batch_axes_and_footprint_units_are_explicit() -> None:
    metrics = _metrics()
    batch = batch_throughput_curve(metrics)
    footprint = footprint_cost_bars(metrics)

    assert batch.layout.yaxis.title.text == "throughput (rows/s)"
    assert batch.layout.yaxis2.title.text == "p50 latency (s/request)"
    assert footprint.layout.yaxis.title.text == "RSS (MB)"
    assert footprint.layout.yaxis2.title.text == "image size (MB)"
    assert footprint.layout.yaxis3.title.text == "USD per 1k predictions"
