"""Determinism: the synthetic path is byte-stable and results repeat exactly."""

import json

from data_engineering.data import rows_equal
from data_engineering.harness import run_benchmark
from data_engineering.synthetic import synthetic_checksum, trips_frame
from data_engineering.tasks import TASKS_BY_NAME
from portfolio_core.synthetic import checksum_of_frame


def test_generator_is_seeded() -> None:
    """Same seed → same canonical frame checksum; different seed differs."""
    a = trips_frame(seed=42, n=2_000)
    b = trips_frame(seed=42, n=2_000)
    c = trips_frame(seed=7, n=2_000)
    assert checksum_of_frame(a) == checksum_of_frame(b)
    assert checksum_of_frame(a) != checksum_of_frame(c)
    assert synthetic_checksum(42, 2_000) == checksum_of_frame(a)


def test_harness_results_repeat(tiny_bundle, fast_cfg, tmp_path) -> None:
    """Two full harness runs produce equivalent canonical results (no timings)."""

    def results(run: int):
        cells = run_benchmark(
            tiny_bundle,
            fast_cfg,
            repeats=1,
            probes=0,
            workdir=tmp_path / f"work-{run}",
        )
        return {f"{c.task}/{c.engine}": c.result_rows for c in cells}

    first = results(0)
    second = results(1)
    assert first.keys() == second.keys()
    for key in first:
        assert rows_equal(first[key], second[key]), f"{key}: results drifted across runs"


def test_cell_repeats_are_identical(tiny_bundle, tmp_path) -> None:
    """Repeated runs of one task inside one cell return identical rows."""
    from data_engineering.harness import run_cell

    task = TASKS_BY_NAME["window"]
    for engine in ("pandas", "polars", "duckdb"):
        cell = run_cell(task, engine, tiny_bundle, tmp_path / engine, repeats=3, probes=0)
        assert len(cell.times) == 3
        # determinism gate passed → single canonical result for the cell
        assert cell.result_rows


def test_cli_evaluate_twice_matches(tmp_path) -> None:
    """End-to-end: two --synthetic CLI runs agree on everything except timings."""
    from data_engineering.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    outputs = []
    for i in range(2):
        out_dir = tmp_path / f"run-{i}"
        result = runner.invoke(
            app,
            [
                "evaluate",
                "--synthetic",
                "--reports-dir",
                str(out_dir),
                "--task",
                "groupby",
                "--task",
                "read_parquet",
                "--repeats",
                "1",
                "--no-probes",
            ],
        )
        assert result.exit_code == 0, result.output
        metrics = json.loads((out_dir / "metrics.json").read_text())
        metrics.pop("engines")  # version strings; not part of the determinism claim
        metrics.pop("summary")  # derived from timings by definition
        strip(metrics)
        for block in metrics["tasks"].values():
            for eng in block["engines"].values():
                eng.pop("result")  # floats compared with tolerance below
        outputs.append(metrics)
    assert outputs[0] == outputs[1]

    # Float results: tolerant equality across the two full CLI processes.
    raw_a = json.loads((tmp_path / "run-0/metrics.json").read_text())
    raw_b = json.loads((tmp_path / "run-1/metrics.json").read_text())
    for task_name, block in raw_a["tasks"].items():
        for engine, eng in block["engines"].items():
            other = raw_b["tasks"][task_name]["engines"][engine]
            assert rows_equal(eng["result"], other["result"]), (
                f"{task_name}/{engine}: results drifted between CLI runs"
            )


def strip(node: object) -> None:
    """Drop timing/memory keys in place so only deterministic content compares."""
    if isinstance(node, dict):
        for key in (
            "time_median_s",
            "time_all_s",
            "cold_s",
            "peak_rss_mb",
            "tracemalloc_peak_mb",
            "speedup_vs_pandas",
        ):
            node.pop(key, None)  # type: ignore[union-attr]
        for value in node.values():  # type: ignore[union-attr]
            strip(value)
    elif isinstance(node, list):
        for value in node:
            strip(value)
