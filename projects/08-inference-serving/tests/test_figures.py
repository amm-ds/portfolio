"""Regression tests for the committed serving-report figures."""

import json
from pathlib import Path

from inference_serving.config import load_config
from inference_serving.figures import fig_quality_quant, fig_toks_per_s
from inference_serving.schemas import BenchRun

PROJECT_DIR = Path(__file__).resolve().parents[1]


def _run() -> BenchRun:
    return BenchRun.model_validate(json.loads((PROJECT_DIR / "data/bench_run.json").read_text()))


def test_ttft_and_throughput_use_committed_cells() -> None:
    cfg = load_config(PROJECT_DIR / "params.yaml")
    fig = fig_toks_per_s(_run(), cfg)

    assert len(fig.data) == 8  # four primary models x two panels
    assert fig.layout.yaxis.title.text == "mean TTFT (s)"
    assert fig.layout.yaxis2.title.text == "output tokens/s"
    qwen = next(trace for trace in fig.data if trace.name.startswith("qwen3.6"))
    assert list(qwen.y) == [
        0.0711838552088011,
        0.7331035531242378,
        2.5053648937144315,
        5.729074880221742,
    ]


def test_quality_guardrail_is_a_dark_pass_fail_table() -> None:
    cfg = load_config(PROJECT_DIR / "params.yaml")
    fig = fig_quality_quant(_run(), cfg)

    assert len(fig.data) == 1
    assert fig.data[0].type == "table"
    assert list(fig.data[0].cells.values[1]) == ["PASS", "PASS", "PASS"]
    assert list(fig.data[0].cells.values[2]) == ["PASS", "PASS", "PASS"]
    assert list(fig.data[0].cells.values[4]) == [0, 0, 0]
    assert fig.data[0].header.fill.color == "#1e293b"
    assert fig.data[0].header.font.color == "#f1f5f9"
    assert fig.data[0].cells.fill.color == "#0f172a"
    assert fig.data[0].cells.font.color == "#e2e8f0"
    assert fig.layout.margin.l == 24
    assert fig.layout.margin.r == 24


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed figure payloads (patched without a full re-run) must agree
    with the numbers in their own traces, and with the generator strings."""
    figures = PROJECT_DIR / "reports" / "figures"

    toks = json.loads((figures / "toks_per_s.json").read_text())
    throughput = {
        trace["name"]: dict(zip(trace["x"], trace["y"], strict=True))
        for trace in toks["data"]
        if trace.get("yaxis") == "y2"
    }
    leaders = {
        max(throughput, key=lambda name: throughput[name][level])
        for level in next(iter(throughput.values()))
    }
    assert leaders == {"qwen3.6:35b-a3b-q4_K_M (llamacpp)"}
    title = toks["layout"]["title"]["text"]
    assert "4-bit MoE leads throughput at every concurrency level" in title

    latency = json.loads((figures / "latency_concurrency.json").read_text())
    moe = next(t for t in latency["data"] if "a3b" in t["name"])
    p95 = dict(zip(moe["x"], moe["y"], strict=True))
    title = latency["layout"]["title"]["text"]
    assert f"from {p95[1]:.2f} s (1 request)" in title
    assert f"to {p95[8]:.2f} s (8 requests)" in title

    panel = json.loads((figures / "engine_panel.json").read_text())
    tok_s = next(t for t in panel["data"] if t.get("yaxis") == "y2")
    by_series = dict(zip(tok_s["x"], tok_s["y"], strict=True))
    mlx = next(v for k, v in by_series.items() if "mlx" in k)
    q8 = next(v for k, v in by_series.items() if "q8_0" in k)
    assert f"{mlx / q8:.1f}\u00d7 the tokens/s" in panel["layout"]["title"]["text"]
