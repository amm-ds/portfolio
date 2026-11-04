"""Typer CLI: fetch-data, evaluate (--synthetic CI track, --scalability), build-report."""

import json
import shutil
import time
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml  # type: ignore[import-untyped]
from portfolio_core.logging import get_logger, setup_logging

from data_engineering.config import DEConfig
from data_engineering.data import DataBundle
from data_engineering.engines import adapter_names
from data_engineering.fetch import fetch_data, load_real_bundle
from data_engineering.figures import build_figures
from data_engineering.harness import run_benchmark
from data_engineering.metrics import (
    BenchmarkRecord,
    build_metadata,
    build_metrics,
    write_record,
)
from data_engineering.report import build_report, build_report_offline
from data_engineering.scalability import (
    build_scalability_metrics,
    run_scalability,
    scalability_protocol_statement,
)
from data_engineering.synthetic import (
    synthetic_checksum,
    write_dataset_contract,
    write_synthetic_dataset,
)

logger = get_logger(__name__)

app = typer.Typer(
    help="Data-engineering benchmark: pandas vs Polars vs DuckDB vs sqlite3 on one task contract."
)

OptParams = Annotated[Path, typer.Option(help="YAML file with config keys.")]


def load_config(params_file: Path = Path("params.yaml")) -> DEConfig:
    """Build DEConfig from params.yaml (if present)."""
    data: dict[str, Any] = {}
    if params_file.exists():
        data = yaml.safe_load(params_file.read_text()) or {}
        logger.info("load_config: %s (%d keys)", params_file, len(data))
    return DEConfig(**data)


def _synthetic_bundle(cfg: DEConfig) -> DataBundle:
    """Materialize the seeded synthetic track into its own data/synthetic dir."""
    out_dir = cfg.data_dir / "synthetic"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    trips, _zones = write_synthetic_dataset(cfg.seed, cfg.n_synthetic_rows, out_dir)
    checksum = synthetic_checksum(cfg.seed, cfg.n_synthetic_rows)
    write_dataset_contract(
        out_dir,
        source=(
            f"synthetic://data_engineering.trips_frame(seed={cfg.seed}, n={cfg.n_synthetic_rows})"
        ),
        n_rows=len(trips),
        checksum=checksum,
        license_text="Synthetic — generated locally by a seeded generator, no license",
    )
    bundle = DataBundle(
        data_dir=out_dir,
        n_rows=len(trips),
        checksum_sha256=checksum,
        source=(f"synthetic://trips_frame?seed={cfg.seed}&n={cfg.n_synthetic_rows}"),
        license="Synthetic (seeded generator)",
        notes="CI fast path: seeded synthetic track; canonical-frame checksum pinned.",
    )
    bundle.validate()
    return bundle


@app.command(name="fetch-data")
def fetch_data_cmd(params_file: OptParams = Path("params.yaml")) -> None:
    """Download the pinned NYC TLC slice and derive the prepared layout."""
    cfg = load_config(params_file)
    setup_logging(cfg.log_level)
    bundle = fetch_data(cfg)
    typer.echo(
        f"fetched + prepared {bundle.n_rows:,} rows -> {cfg.data_dir} "
        f"(sha256 {bundle.checksum_sha256[:12]}…)"
    )


@app.command()
def evaluate(
    synthetic: Annotated[
        bool, typer.Option("--synthetic", help="Seeded synthetic track (CI fast path).")
    ] = False,
    scalability: Annotated[
        bool,
        typer.Option(
            "--scalability",
            help="Also run the 1M/3M/10M seeded scalability study and merge it into metrics.json.",
        ),
    ] = False,
    params_file: OptParams = Path("params.yaml"),
    reports_dir: Annotated[
        Path | None, typer.Option("--reports-dir", help="Override the reports directory.")
    ] = None,
    repeats: Annotated[int | None, typer.Option("--repeats", help="Override warm repeats.")] = None,
    engines: Annotated[
        list[str] | None, typer.Option("--engine", help="Restrict to these engines.")
    ] = None,
    tasks: Annotated[
        list[str] | None, typer.Option("--task", help="Restrict to these tasks.")
    ] = None,
    no_probes: Annotated[
        bool, typer.Option("--no-probes", help="Skip fresh-process memory/cold probes.")
    ] = False,
) -> None:
    """Run the benchmark (real track by default; --synthetic for CI)."""
    cfg = load_config(params_file)
    setup_logging(cfg.log_level)
    out_dir = reports_dir or cfg.reports_dir

    if synthetic:
        bundle = _synthetic_bundle(cfg)
        track = "synthetic"
    else:
        bundle = load_real_bundle(cfg)
        track = "real"

    t0 = time.perf_counter()
    cells = run_benchmark(
        bundle,
        cfg,
        engines=engines,
        task_names=tasks,
        repeats=repeats,
        probes=0 if no_probes else None,
    )
    runtime_s = time.perf_counter() - t0

    # Scalability study: measured on demand; a run without the flag preserves a
    # previously committed scalability block instead of wiping it.
    scale_block: dict[str, Any] | None = None
    scale_meta: dict[str, Any] | None = None
    scale_runtime_s = 0.0
    if scalability and not synthetic:
        scale_runs, scale_runtime_s = run_scalability(cfg, engines=engines)
        scale_block = build_scalability_metrics(scale_runs)
        scale_meta = {
            "protocol_statement": scalability_protocol_statement(cfg),
            "seed": cfg.seed,
            "sizes": scale_block["sizes"],
            "tasks": list(scale_block["tasks"]),
            "runtime_s": round(scale_runtime_s, 3),
        }
    else:
        existing = _load_existing(out_dir)
        if existing is not None and "scalability" in existing[0]:
            scale_block = existing[0]["scalability"]
        if existing is not None and "scalability" in existing[1]:
            scale_meta = existing[1]["scalability"]

    metrics = build_metrics(cells, cfg, bundle, scalability=scale_block)
    metadata = build_metadata(
        cfg, bundle, track=track, runtime_s=runtime_s, cells=cells, scalability=scale_meta
    )
    record = BenchmarkRecord(metrics=metrics, metadata=metadata)
    write_record(record, out_dir)
    figures = build_figures(metrics)
    from data_engineering.report import write_figures

    write_figures(figures, out_dir / "figures")
    build_report(
        metrics, metadata, figures, out_dir, project_dir=Path(__file__).resolve().parents[2]
    )

    summary = metrics["summary"]["by_engine"]
    typer.echo(
        "geomean speedup vs pandas: "
        + ", ".join(f"{e}=x{summary[e]['geomean_speedup_vs_pandas']}" for e in summary)
    )
    msg = (
        f"benchmark phase {runtime_s:.1f}s — artifacts in {out_dir} "
        f"(metrics.json, evaluation_metadata.json, report.html, figures/)"
    )
    if scalability:
        msg += f"; scalability phase {scale_runtime_s:.1f}s"
    typer.echo(msg)


def _load_existing(out_dir: Path) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Previously committed metrics/metadata, for preserving the scalability block."""
    metrics_path = out_dir / "metrics.json"
    metadata_path = out_dir / "evaluation_metadata.json"
    if not metrics_path.exists() or not metadata_path.exists():
        return None
    try:
        return (
            json.loads(metrics_path.read_text()),
            json.loads(metadata_path.read_text()),
        )
    except json.JSONDecodeError:
        return None


@app.command(name="build-report")
def build_report_cmd(
    params_file: OptParams = Path("params.yaml"),
    reports_dir: Annotated[Path | None, typer.Option("--reports-dir")] = None,
) -> None:
    """Rebuild report.html + results.md from committed artifacts (offline)."""
    cfg = load_config(params_file)
    out_dir = reports_dir or cfg.reports_dir
    path = build_report_offline(out_dir, project_dir=Path(__file__).resolve().parents[2])
    typer.echo(f"report rebuilt at {path}")


@app.command(name="show-engines")
def show_engines() -> None:
    """Print registered engines and runtime versions (offline)."""
    from data_engineering.engines import engine_versions

    registered = adapter_names()
    versions = engine_versions()
    typer.echo(f"engines: {registered}")
    typer.echo(json.dumps(versions, indent=2))


if __name__ == "__main__":
    app()
