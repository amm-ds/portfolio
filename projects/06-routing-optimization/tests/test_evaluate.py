"""Evaluation tests: name normalization, best-known loading, gap math, figures."""

import json
from pathlib import Path

import polars as pl
import pytest
from routing_optimization.cli import download_instances
from routing_optimization.config import VRPConfig
from routing_optimization.evaluate import (
    canonical_instance_name,
    convergence_figure,
    eda_instance_map_figure,
    evaluate_instance,
    gap_figure,
    gap_pct,
    load_best_known,
    route_map_figure,
    run_dq,
    runtime_figure,
    solve_with_timing,
    solver_profile_figure,
)
from routing_optimization.schemas import Problem
from routing_optimization.solver import two_opt


def test_canonical_instance_name() -> None:
    assert canonical_instance_name("C101") == "C101"
    assert canonical_instance_name("C1_01") == "C101"  # registry/file style
    assert canonical_instance_name("c101.txt") == "C101"  # archive member style
    assert canonical_instance_name("rc108") == "RC108"


def test_gap_pct_math() -> None:
    assert gap_pct(1100.0, 1000.0) == pytest.approx(10.0)
    assert gap_pct(1000.0, 1000.0) == pytest.approx(0.0)
    assert gap_pct(828.94, 828.94) == pytest.approx(0.0)


def test_load_best_known_skips_comments(tmp_path: Path) -> None:
    csv_path = tmp_path / "solomon100.csv"
    csv_path.write_text(
        "# comment line\n"
        "instance,best_known,source\n"
        "C101,828.94,Solomon1987\n"
        "RC1_02,1554.75,JUSTC\n"
    )
    table = load_best_known(csv_path)
    assert table == {"C101": 828.94, "RC102": 1554.75}


def test_run_dq_passes_on_tiny(tiny_problem: Problem) -> None:
    report = run_dq(tiny_problem)
    assert report.passed
    assert report.n_rows == 6
    report.raise_if_failed()


def test_solve_with_timing_returns_four_runs(tiny_problem: Problem) -> None:
    runs, plans = solve_with_timing(tiny_problem, max_iterations=200, seed=42)
    assert {r.solver for r in runs} == {
        "nearest_neighbor",
        "clarke_wright",
        "randomized",
        "two_opt",
    }
    assert all(r.runtime_s >= 0.0 for r in runs)
    assert set(plans) == {"nearest_neighbor", "clarke_wright", "randomized", "two_opt"}
    two_opt_run = next(r for r in runs if r.solver == "two_opt")
    assert two_opt_run.base_solver in {"nearest_neighbor", "clarke_wright"}


def test_evaluate_instance_with_best_known(tiny_problem: Problem) -> None:
    evaln = evaluate_instance(tiny_problem, max_iterations=200, best_known=10.0)
    assert evaln.best_known == 10.0
    gaps = [gap_pct(r.total_distance, 10.0) for r in evaln.runs]
    assert all(g > 0.0 for g in gaps)  # tiny optimum is well above 10 distance units
    assert evaln.best_routes is not None


def test_figures_build_on_tiny_data(tiny_problem: Problem) -> None:
    runs, plans = solve_with_timing(tiny_problem, max_iterations=200, seed=42)
    gap_rows = pl.DataFrame({"instance": "TINY", "solver": r.solver, "gap_pct": 1.0} for r in runs)
    rt_rows = pl.DataFrame(
        {"instance": "TINY", "solver": r.solver, "runtime_s": r.runtime_s} for r in runs
    )
    dist_rows = pl.DataFrame(
        {"instance": "TINY", "solver": r.solver, "distance": r.total_distance} for r in runs
    )
    trace: list[float] = []
    improved = two_opt(tiny_problem, plans["nearest_neighbor"], max_iterations=200, trace=trace)
    fig_gap = gap_figure(gap_rows)
    fig_rt = runtime_figure(rt_rows)
    fig_map = route_map_figure(tiny_problem, plans["two_opt"].routes, title="TINY map")
    fig_eda = eda_instance_map_figure(tiny_problem)
    fig_profile = solver_profile_figure(dist_rows)
    fig_conv = convergence_figure(
        {"untuned": trace, "tuned": [*trace, improved.total_distance]},
        "TINY",
    )
    for fig in (fig_gap, fig_rt, fig_map, fig_eda, fig_profile, fig_conv):
        assert fig.data, "figure has traces"


def _offline_config(tmp_path: Path) -> VRPConfig:
    """A config pointed at a local archive so the download test needs no network."""
    archive = tmp_path / "mirror" / "solomon-100.zip"
    archive.parent.mkdir(parents=True)
    import zipfile

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(
            "In/c101.txt",
            "C101\n\nVEHICLE\nNUMBER     CAPACITY\n  25      200\n\nCUSTOMER\n"
            "    0      40  50  0  0  1236  0\n",
        )
    return VRPConfig(
        instances=["C101"],
        raw_dir=tmp_path / "raw",
        download_url=archive.as_uri(),
        best_known_path=tmp_path / "best_known.csv",
        reports_dir=tmp_path / "reports",
    )


def test_download_instances_from_local_archive(tmp_path: Path) -> None:
    cfg = _offline_config(tmp_path)
    written = download_instances(cfg)
    assert [p.name for p in written] == ["C101.txt"]
    assert (cfg.raw_dir / "dataset_card.json").exists()
    card = json.loads((cfg.raw_dir / "dataset_card.json").read_text())
    assert card["n_rows"] == 100  # 100 customers x 1 instance
    assert card["checksum_sha256"]


def test_solve_and_evaluate_offline(tmp_path: Path, tiny_text: str) -> None:
    """End-to-end offline: raw file in, all evaluation artifacts out."""
    from routing_optimization.evaluate import run_evaluate, run_solve

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "TINY.txt").write_text(tiny_text)
    (tmp_path / "best_known.csv").write_text("instance,best_known\nTINY,500.0\n")
    cfg = VRPConfig(
        instances=["TINY"],
        raw_dir=raw,
        best_known_path=tmp_path / "best_known.csv",
        reports_dir=tmp_path / "reports",
        map_instance="TINY",
        convergence_instances=["TINY"],
        params_path=tmp_path / "params.yaml",
        hpo_trials=6,
        alns_max_iterations=30,
        alns_destroy_q=2,
        alns_hpo_trials=3,
        alns_hpo_instances=["TINY"],
    )
    run_solve(cfg)
    assert (cfg.reports_dir / "solutions.json").exists()
    assert (cfg.reports_dir / "dq.md").exists()
    metrics = run_evaluate(cfg)
    data = json.loads(metrics.read_text())
    assert data["instances"]["TINY"]["best_known"] == 500.0
    assert data["instances"]["TINY"]["best_solver"] in {
        "nearest_neighbor",
        "clarke_wright",
        "randomized",
        "two_opt",
        "two_opt_tuned",
        "alns",
    }
    assert set(data["instances"]["TINY"]["solvers"]) == {
        "nearest_neighbor",
        "clarke_wright",
        "randomized",
        "two_opt",
        "two_opt_tuned",
        "alns",
    }
    # the tuned runs are never worse than the randomized floor, and the HPO
    # winners are persisted to the (overridden) params.yaml
    solvers = data["instances"]["TINY"]["solvers"]
    assert solvers["two_opt_tuned"]["distance"] <= solvers["randomized"]["distance"]
    assert solvers["alns"]["distance"] <= solvers["randomized"]["distance"]
    assert data["tuning"]["solver_best"]["restarts"] >= 1
    assert data["tuning"]["alns_best"]["segment_length"] >= 5
    assert "families" in data
    params = (tmp_path / "params.yaml").read_text()
    assert "solver_best:" in params
    assert "alns_best:" in params
    for artifact in (
        "results.md",
        "report.html",
        "figures/gap_pct.html",
        "figures/gap_pct.json",
        "figures/eda_instance_map.html",
        "figures/eda_instance_map.json",
        "figures/route_map_TINY.html",
        "figures/route_map_TINY.json",
        "figures/runtime.html",
        "figures/runtime.json",
        "figures/solver_profile.html",
        "figures/solver_profile.json",
        "figures/convergence_TINY.html",
        "figures/convergence_TINY.json",
        "figures/family_gap.html",
        "figures/family_gap.json",
    ):
        assert (cfg.reports_dir / artifact).exists(), artifact
