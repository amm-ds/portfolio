"""Regression tests for serving-figure bands, axes, and units."""

import json
from pathlib import Path

import pytest
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


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed figure titles agree with the committed metrics they depict."""
    reports = Path(__file__).resolve().parents[1] / "reports"
    figures = reports / "figures"
    metrics = json.loads((reports / "metrics.json").read_text())

    latency = json.loads((figures / "latency_concurrency_lines.json").read_text())
    ltitle = latency["layout"]["title"]["text"]
    assert ltitle.startswith("p95 stays under")
    c4_p95 = max(metrics["serving"][b]["concurrency"]["c4"]["p95_s"] for b in ("native", "onnx"))
    assert f"under {c4_p95 * 1000:.0f} ms" in ltitle
    p95 = [t for t in latency["data"] if t["name"].endswith("p95")]
    assert len(p95) == 2
    for trace in p95:
        by_c = dict(zip(trace["x"], trace["y"], strict=True))
        assert all(v < 2 * c4_p95 for c, v in by_c.items() if c <= 4)
        assert by_c[64] > by_c[16]  # the climb past 16

    batch = json.loads((figures / "batch_throughput_curve.json").read_text())
    btitle = batch["layout"]["title"]["text"]
    largest = max(int(c[1:]) for c in metrics["serving"]["native"]["batch"])
    native_t = metrics["serving"]["native"]["batch"][f"b{largest}"]["throughput_rps"]
    onnx_t = metrics["serving"]["onnx"]["batch"][f"b{largest}"]["throughput_rps"]
    assert btitle.startswith(
        f"Batches of {largest} rows reach {native_t / 1000:.0f}k rows/s native"
    )
    assert f"{onnx_t / 1000:.0f}k ONNX" in btitle
    throughput = [t for t in batch["data"] if max(t["y"]) > 1000]
    assert len(throughput) == 2
    seen = []
    for trace in throughput:
        seen.append(dict(zip(trace["x"], trace["y"], strict=True))[largest])
    # the two traces are the two backends' throughputs at the largest batch
    assert sorted(seen) == pytest.approx(sorted([native_t, onnx_t]))

    slope = json.loads((figures / "backend_comparison_slope.json").read_text())
    stitle = slope["layout"]["title"]["text"]
    devs = []
    for trace in slope["data"]:
        native_p50, onnx_p50 = trace["y"]
        devs.append(abs(onnx_p50 / native_p50 - 1.0))
    assert f"at most {max(devs):.0%}" in stitle

    footprint = json.loads((figures / "footprint_cost_bars.json").read_text())
    ftitle = footprint["layout"]["title"]["text"]
    docker = metrics["docker"]
    assert f"{docker['total_mb']:.0f} MB" in ftitle
    assert f"{docker['venv_mb']:.0f} MB" in ftitle
    venv_bar = next(t for t in footprint["data"] if "venv (deps)" in t["x"])
    assert venv_bar["y"][venv_bar["x"].index("venv (deps)")] > 0.5 * docker["total_mb"]
