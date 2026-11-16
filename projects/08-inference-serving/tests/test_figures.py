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


def test_quality_guardrail_is_a_pass_fail_table() -> None:
    cfg = load_config(PROJECT_DIR / "params.yaml")
    fig = fig_quality_quant(_run(), cfg)

    assert len(fig.data) == 1
    assert fig.data[0].type == "table"
    assert list(fig.data[0].cells.values[1]) == ["PASS", "PASS", "PASS"]
    assert list(fig.data[0].cells.values[2]) == ["PASS", "PASS", "PASS"]
    assert list(fig.data[0].cells.values[4]) == [0, 0, 0]
