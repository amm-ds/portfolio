"""Harness statistics math, offline, against fixed fixtures."""

from model_serving.artifacts import probe_grid
from model_serving.bench import (
    RequestRecord,
    median,
    median_cell,
    payloads_from_grid,
    percentile,
    summarize_cell,
)


def test_percentile_nearest_rank_fixture() -> None:
    values = [0.1, 0.5, 0.2, 0.4, 0.3]  # sorted: 0.1..0.5
    assert percentile(values, 0.50) == 0.3  # ceil(0.5*5)=3
    assert percentile(values, 0.95) == 0.5  # ceil(4.75)=5
    assert percentile(values, 0.99) == 0.5
    assert percentile(values, 1.0) == 0.5
    assert percentile(values, 0.20) == 0.1  # rank = ceil(0.2*5) = 1
    assert percentile([7.0], 0.50) == 7.0
    assert percentile([], 0.50) is None


def test_median_fixtures() -> None:
    assert median([3.0, 1.0, 2.0]) == 2.0
    assert median([4.0, 1.0, 2.0, 3.0]) == 2.5
    assert median([2.0]) == 2.0


def test_summarize_cell_fixtures() -> None:
    records = [
        RequestRecord(cell="c1", latency_s=0.10),
        RequestRecord(cell="c1", latency_s=0.20),
        RequestRecord(cell="c1", latency_s=0.30, error="timeout"),
        RequestRecord(cell="c1", latency_s=0.40),
    ]
    summary = summarize_cell(records, "c1", wall_time_s=2.0)
    assert summary.n_requests == 4
    assert summary.n_errors == 1
    assert summary.error_rate == 0.25
    assert summary.p50_s == 0.2
    assert summary.p95_s == 0.4
    assert summary.throughput_rps == 1.5  # 3 ok / 2 s


def test_median_cell_takes_median_of_repeats() -> None:
    repeats = [
        summarize_cell(
            [RequestRecord(cell="c1", latency_s=0.1 * (r + 1) + i * 0.001) for i in range(10)],
            "c1",
            wall_time_s=1.0,
        )
        for r in range(3)
    ]
    merged = median_cell(repeats, "c1")
    assert merged["repeats"] == 3
    assert merged["p50_s"] == sorted(s.p50_s for s in repeats if s.p50_s is not None)[1]


def test_payload_stream_is_seeded_and_schema_legal() -> None:
    from model_serving.service.schemas import NUMERIC_FIELDS, FeatureRow

    grid = probe_grid(16, 42, NUMERIC_FIELDS)
    a = payloads_from_grid(grid, 12, 7)
    b = payloads_from_grid(grid, 12, 7)
    assert a == b
    for row in a:
        FeatureRow.model_validate(row)  # raises if the stream is out of contract
