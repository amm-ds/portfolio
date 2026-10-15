"""Offline tests for the aggregation math and output validation."""

from __future__ import annotations

import pytest
from inference_serving.bench import build_cell, check_output, percentile
from inference_serving.config import BenchConfig
from inference_serving.report import electricity_cost_per_mtok
from inference_serving.schemas import BenchPrompt, RequestRecord


def test_percentile_nearest_rank() -> None:
    vals = [0.1 * i for i in range(1, 11)]  # 0.1 .. 1.0
    assert percentile(vals, 0.50) == 0.5
    assert percentile(vals, 0.90) == 0.9  # ceil(9.0)=9
    assert percentile(vals, 0.95) == 1.0  # ceil(9.5)=10 → max (nearest-rank)
    assert percentile(vals, 1.00) == 1.0
    assert percentile([2.0], 0.99) == 2.0
    assert percentile([], 0.95) is None


def _record(**kw: object) -> RequestRecord:
    base: dict[str, object] = {
        "model": "m",
        "prompt_id": "p",
        "repeat": 0,
        "ttft_s": 0.1,
        "latency_s": 1.0,
        "output_tokens": 10,
        "schema_valid": True,
        "quality_ok": True,
    }
    base.update(kw)
    return RequestRecord(**base)  # type: ignore[arg-type]


def test_build_cell_metrics() -> None:
    records = [
        _record(latency_s=1.0, output_tokens=10, ttft_s=0.2),
        _record(latency_s=2.0, output_tokens=20, ttft_s=0.4),
        _record(latency_s=3.0, output_tokens=30, ttft_s=0.6),
        _record(latency_s=4.0, output_tokens=40, ttft_s=0.8),
        _record(error="timeout"),
    ]
    cell = build_cell(records, model="m", engine="llamacpp", concurrency=2, wall_time_s=5.0)
    assert cell.n_requests == 5
    assert cell.n_failures == 1
    assert cell.p50_latency_s == 2.0
    assert cell.p95_latency_s == 4.0  # nearest-rank over 4 samples: ceil(.95*4)=4
    assert cell.p99_latency_s == 4.0
    assert cell.mean_ttft_s == pytest.approx(0.5)
    # aggregate: 100 tokens over 5s wall; per-request: 10/1, 20/2, 30/3, 40/4 → 10.0 each
    assert cell.agg_tok_per_s == pytest.approx(20.0)
    assert cell.mean_req_tok_per_s == pytest.approx(10.0)
    assert cell.schema_valid_rate == 1.0
    assert cell.quality_rate == 1.0
    assert cell.total_output_tokens == 100


def test_build_cell_all_failed() -> None:
    cell = build_cell(
        [_record(error="timeout")], model="m", engine="mlx", concurrency=1, wall_time_s=1.0
    )
    assert cell.n_failures == 1
    assert cell.p95_latency_s is None
    assert cell.agg_tok_per_s == 0.0
    assert cell.schema_valid_rate == 0.0


def test_check_output_valid_and_quality() -> None:
    prompt = BenchPrompt(id="p", prompt="?", expected_keywords=["paris"])
    ok = '{"answer": "The capital is Paris.", "confidence": 0.9, "citation": "Atlas p.12"}'
    assert check_output(ok, prompt) == (True, True)
    fenced = f"```json\n{ok}\n```"
    assert check_output(fenced, prompt) == (True, True)
    wrong_kw = '{"answer": "The capital is Lyon.", "confidence": 0.9, "citation": "Atlas"}'
    assert check_output(wrong_kw, prompt) == (True, False)
    assert check_output("not json", prompt) == (False, False)
    bad_conf = '{"answer": "Paris.", "confidence": 1.5, "citation": "Atlas"}'
    assert check_output(bad_conf, prompt) == (False, False)


def test_electricity_cost_per_mtok() -> None:
    # 100 tok/s → 1e6/100/3600 h = 2.78 h x 0.1 kW x $0.30 = $0.0833
    cost = electricity_cost_per_mtok(100.0, usd_per_kwh=0.30, system_load_watts=100.0)
    assert cost == pytest.approx(0.0833, abs=1e-3)
    assert electricity_cost_per_mtok(0.0, usd_per_kwh=0.30, system_load_watts=100.0) is None


def test_bench_config_defaults() -> None:
    cfg = BenchConfig()
    assert cfg.request_timeout_s == 180.0
    assert cfg.concurrency(full=False) == [1, 4, 8]
    assert cfg.concurrency(full=True) == [1, 2, 4, 8]
