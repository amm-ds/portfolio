"""Harness + metrics + figures schema: one probed cell grid end to end."""

import json
import math

from data_engineering.config import DEConfig
from data_engineering.data import DataBundle
from data_engineering.figures import build_figures
from data_engineering.harness import run_benchmark
from data_engineering.metrics import (
    BenchmarkRecord,
    build_metadata,
    build_metrics,
    load_metrics,
    write_record,
)
from data_engineering.report import (
    build_report,
    build_report_offline,
    cold_table,
    headline_table,
    memory_table,
    write_figures,
)
from data_engineering.tasks import TASKS


def _run_grid(bundle: DataBundle, cfg: DEConfig, tmp_path, probes: int = 1):
    return run_benchmark(
        bundle,
        cfg,
        repeats=2,
        probes=probes,
        workdir=tmp_path / "work",
    )


def test_metrics_schema(tiny_bundle: DataBundle, fast_cfg: DEConfig, tmp_path) -> None:
    """Every task-by-engine cell carries time, cold (IO), memory and a result."""
    cells = _run_grid(tiny_bundle, fast_cfg, tmp_path, probes=1)
    assert len(cells) == len(TASKS) * 3
    metrics = build_metrics(cells, fast_cfg, tiny_bundle)

    assert metrics["protocol"] == "engine_benchmark_v1"
    for task in TASKS:
        block = metrics["tasks"][task.name]
        assert block["category"] == task.category
        for engine in ("pandas", "polars", "duckdb"):
            eng = block["engines"][engine]
            assert len(eng["time_all_s"]) == 2, f"{task.name}/{engine}: repeats missing"
            assert eng["time_median_s"] > 0
            assert eng["result"], f"{task.name}/{engine}: empty result"
            if task.cold_measurable:
                assert eng["cold_s"] is not None and eng["cold_s"] > 0
                assert eng["peak_rss_mb"] is not None and eng["peak_rss_mb"] > 0
            assert eng["speedup_vs_pandas"] > 0
        # speedup math: pandas is the x1 baseline (stored rounded to 3 dp)
        base = block["engines"]["pandas"]["time_median_s"]
        for engine in ("polars", "duckdb"):
            got = block["engines"][engine]["speedup_vs_pandas"]
            expected = round(base / block["engines"][engine]["time_median_s"], 3)
            assert math.isclose(got, expected, abs_tol=1e-6)
        assert block["engines"]["pandas"]["speedup_vs_pandas"] == 1.0

    summary = metrics["summary"]
    assert summary["by_engine"]["pandas"]["geomean_speedup_vs_pandas"] == 1.0
    for engine in ("polars", "duckdb"):
        geo = summary["by_engine"][engine]["geomean_speedup_vs_pandas"]
        assert geo is not None and geo > 0
    assert set(summary["fastest_engine_by_task"]) == {t.name for t in TASKS}


def test_metrics_without_probes(tiny_bundle: DataBundle, fast_cfg: DEConfig, tmp_path) -> None:
    """Probes are optional: cold/RSS are None, the rest of the schema holds."""
    cells = _run_grid(tiny_bundle, fast_cfg, tmp_path, probes=0)
    metrics = build_metrics(cells, fast_cfg, tiny_bundle)
    eng = metrics["tasks"]["read_parquet"]["engines"]["pandas"]
    assert eng["cold_s"] is None
    assert eng["peak_rss_mb"] is None
    assert eng["time_median_s"] > 0


def test_metadata_schema(tiny_bundle: DataBundle, fast_cfg: DEConfig, tmp_path) -> None:
    """Metadata carries protocol, versions, hardware and the dataset identity."""
    cells = _run_grid(tiny_bundle, fast_cfg, tmp_path, probes=0)
    meta = build_metadata(fast_cfg, tiny_bundle, track="synthetic", runtime_s=1.5, cells=cells)
    assert meta["protocol"] == "engine_benchmark_v1"
    assert meta["track"] == "synthetic"
    assert meta["seed"] == 42
    assert meta["runtime_s"] == 1.5
    for key in ("platform", "machine", "cpu_count"):
        assert meta["hardware"][key] not in (None, "")
    for engine in ("pandas", "polars", "duckdb", "pyarrow"):
        assert meta["engines"][engine], f"missing version {engine}"
    assert meta["dataset"]["n_rows"] == tiny_bundle.n_rows
    assert meta["dataset"]["prepared_bytes"]["partitioned_files"] >= 28
    # determinism record: one result fingerprint per cell
    assert len(meta["determinism"]) == len(TASKS) * 3


def test_record_round_trip(tiny_bundle: DataBundle, fast_cfg: DEConfig, tmp_path) -> None:
    """metrics.json + evaluation_metadata.json commit and reload."""
    cells = _run_grid(tiny_bundle, fast_cfg, tmp_path, probes=0)
    record = BenchmarkRecord(
        metrics=build_metrics(cells, fast_cfg, tiny_bundle),
        metadata=build_metadata(
            fast_cfg, tiny_bundle, track="synthetic", runtime_s=2.0, cells=cells
        ),
    )
    write_record(record, fast_cfg.reports_dir)
    loaded = load_metrics(fast_cfg.reports_dir)
    assert loaded["protocol"] == "engine_benchmark_v1"
    meta = json.loads((fast_cfg.reports_dir / "evaluation_metadata.json").read_text())
    assert meta["track"] == "synthetic"


def test_figures_schema(tiny_bundle: DataBundle, fast_cfg: DEConfig, tmp_path) -> None:
    """Four figures build from metrics and persist in both payload formats."""
    cells = _run_grid(tiny_bundle, fast_cfg, tmp_path, probes=1)
    metrics = build_metrics(cells, fast_cfg, tiny_bundle)
    figures = build_figures(metrics)
    assert list(figures) == [
        "runtime_by_task",
        "memory_by_task",
        "speedup_vs_pandas",
        "io_cold_warm",
    ]
    for name, fig in figures.items():
        assert len(fig.data) >= 3, f"{name}: expected grouped traces"
        assert fig.layout.title.text, f"{name}: missing title"
    out = fast_cfg.reports_dir / "figures"
    write_figures(figures, out)
    for name in figures:
        assert (out / f"{name}.json").exists()
        assert (out / f"{name}.html").exists()


def test_report_tables_and_offline_rebuild(
    tiny_bundle: DataBundle, fast_cfg: DEConfig, tmp_path
) -> None:
    """Markdown tables render; report.html builds from live and committed state."""
    from pathlib import Path

    cells = _run_grid(tiny_bundle, fast_cfg, tmp_path, probes=1)
    metrics = build_metrics(cells, fast_cfg, tiny_bundle)
    meta = build_metadata(fast_cfg, tiny_bundle, track="synthetic", runtime_s=3.0, cells=cells)

    assert "| task | pandas | Polars | DuckDB |" in headline_table(metrics)
    assert "| task | pandas | Polars | DuckDB |" in memory_table(metrics)
    assert "cold → warm" in cold_table(metrics)

    figures = build_figures(metrics)
    write_figures(figures, fast_cfg.reports_dir / "figures")
    write_record(BenchmarkRecord(metrics=metrics, metadata=meta), fast_cfg.reports_dir)
    project_dir = Path(__file__).resolve().parents[1]
    path = build_report(metrics, meta, figures, fast_cfg.reports_dir, project_dir=project_dir)
    assert path.exists() and "<h1>" in path.read_text()

    # Offline rebuild from committed artifacts reproduces the report.
    rebuilt = build_report_offline(fast_cfg.reports_dir, project_dir=project_dir)
    assert rebuilt.exists()
