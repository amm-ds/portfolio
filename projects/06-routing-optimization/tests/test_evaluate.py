"""Evaluation tests: name normalization, best-known loading, gap math, figures."""

import base64
import json
import statistics
import struct
from pathlib import Path

import polars as pl
import pytest
from routing_optimization.cli import download_instances
from routing_optimization.config import VRPConfig
from routing_optimization.evaluate import (
    InstanceEvaluation,
    SolverRun,
    _family_rows,
    _intervals_block,
    _mean_gap_interval,
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
from routing_optimization.reporting import (
    family_markdown,
    results_markdown,
    solver_display_name,
    summary_markdown,
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


def test_family_rows_aggregate_instances_to_family_solver_means() -> None:
    evaluations = [
        InstanceEvaluation(
            instance="C101",
            n_customers=100,
            vehicle_capacity=200.0,
            best_known=1000.0,
            best_known_vehicles=10,
            runs=[SolverRun("alns", 1010.0, 11, 1.0), SolverRun("two_opt", 1100.0, 12, 0.1)],
        ),
        InstanceEvaluation(
            instance="C102",
            n_customers=100,
            vehicle_capacity=200.0,
            best_known=1000.0,
            best_known_vehicles=10,
            runs=[SolverRun("alns", 1030.0, 11, 1.0), SolverRun("two_opt", 1200.0, 13, 0.1)],
        ),
    ]
    rows = _family_rows(evaluations).sort(["solver", "family"])
    assert rows.to_dicts() == [
        {"family": "C1", "solver": "alns", "gap_pct": pytest.approx(2.0), "veh_delta": 1.0},
        {"family": "C1", "solver": "two_opt", "gap_pct": pytest.approx(15.0), "veh_delta": 2.5},
    ]


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
    for fig in (fig_gap, fig_rt, fig_profile):
        assert all(trace.type == "box" for trace in fig.data)
        assert fig.layout.showlegend is False


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
        ortools_time_limit_s=2.0,
    )
    run_solve(cfg)
    assert (cfg.reports_dir / "solutions.json").exists()
    assert (cfg.reports_dir / "dq.md").exists()
    frontier = {
        "buckets_s": [1.0],
        "time_cap_s": 1.0,
        "n_instances": 1,
        "alns": {"median": [2.0], "mean": [2.0]},
        "cp_sat": {"median": [3.0], "mean": [3.0]},
    }
    (cfg.reports_dir / "frontier.json").write_text(json.dumps(frontier))
    metrics = run_evaluate(cfg)
    data = json.loads(metrics.read_text())
    assert data["frontier"] == frontier
    assert (cfg.reports_dir / "figures/frontier_gap_time.json").exists()
    assert (cfg.reports_dir / "figures/frontier_gap_time.html").exists()
    assert data["instances"]["TINY"]["best_known"] == 500.0
    assert data["instances"]["TINY"]["best_solver"] in {
        "nearest_neighbor",
        "clarke_wright",
        "randomized",
        "two_opt",
        "two_opt_tuned",
        "alns",
        "ortools_cp",
        "alns_fleet",
    }
    assert set(data["instances"]["TINY"]["solvers"]) == {
        "nearest_neighbor",
        "clarke_wright",
        "randomized",
        "two_opt",
        "two_opt_tuned",
        "alns",
        "ortools_cp",
        "alns_fleet",
    }
    # the tuned runs are never worse than the randomized floor, and the HPO
    # winners are persisted to the (overridden) params.yaml
    solvers = data["instances"]["TINY"]["solvers"]
    assert solvers["two_opt_tuned"]["distance"] <= solvers["randomized"]["distance"]
    assert solvers["alns"]["distance"] <= solvers["randomized"]["distance"]
    assert solvers["alns_fleet"]["distance"] <= solvers["randomized"]["distance"]
    # the unhinted arm is recorded per instance (tiny instance solves; on the
    # real benchmark it reports UNKNOWN honestly when nothing is found)
    unhinted = data["unhinted_cp_sat"]
    assert set(unhinted) == {"TINY"}
    assert unhinted["TINY"]["status"] in ("OPTIMAL", "FEASIBLE")
    assert unhinted["TINY"]["runtime_s"] > 0
    assert "total_distance" in unhinted["TINY"]
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
        "figures/pareto_gap_runtime.html",
        "figures/pareto_gap_runtime.json",
        "figures/alns_convergence_TINY.html",
        "figures/alns_convergence_TINY.json",
    ):
        assert (cfg.reports_dir / artifact).exists(), artifact


def _gap_evaluations() -> list[InstanceEvaluation]:
    return [
        InstanceEvaluation(
            instance=f"C1{i:02d}",
            n_customers=100,
            vehicle_capacity=200.0,
            best_known=1000.0,
            best_known_vehicles=10,
            runs=[
                SolverRun("alns", 1000.0 + 10.0 * i, 11, 1.0),
                SolverRun("ortools_cp", 1000.0 + 10.0 * i, 11, 12.0),
            ],
        )
        for i in range(1, 57)
    ]


def test_mean_gap_interval_is_seed_deterministic() -> None:
    evaluations = _gap_evaluations()
    a = _mean_gap_interval(evaluations)
    b = _mean_gap_interval(evaluations)
    assert a == b  # same seed -> identical interval
    assert a["n_boot"] == 2000 and a["seed"] == 42
    assert a["lo"] <= a["point"] <= a["hi"]
    # A different seed yields a different resample path: the interval is only
    # reproducible because the seed is fixed (removing it breaks determinism).
    c = _mean_gap_interval(evaluations, seed=7)
    assert (c["lo"], c["hi"]) != (a["lo"], a["hi"])


def test_mean_gap_interval_covers_the_committed_mean() -> None:
    evaluations = _gap_evaluations()
    interval = _mean_gap_interval(evaluations)
    # per-instance gaps are 1.0..56.0% -> mean 28.5%, well inside the CI
    assert interval["point"] == pytest.approx(28.5)
    assert interval["lo"] < 28.5 < interval["hi"]


def test_alns_vs_unhinted_interval_is_recorded_not_filled() -> None:
    block = _intervals_block(_gap_evaluations())
    alns_vs = block["alns_vs_unhinted_cp_sat"]
    assert alns_vs["point"] is None and alns_vs["lo"] is None and alns_vs["hi"] is None
    assert "UNKNOWN on all 56" in alns_vs["reason"]


def test_hinted_cp_sat_label_set_whenever_hint_is_used() -> None:
    # The display label must carry the non-independence note in every table.
    assert solver_display_name("ortools_cp") == "ortools_cp (ALNS-hinted; not independent of ALNS)"
    assert solver_display_name("alns") == "alns"  # other keys untouched
    evaluations = _gap_evaluations()[:1]
    for table in (
        summary_markdown(evaluations),
        family_markdown(evaluations),
        results_markdown(evaluations),
    ):
        assert "ortools_cp (ALNS-hinted; not independent of ALNS)" in table


def _decode(arr: object) -> list:
    """Decode a plotly 6 binary array ({"bdata": ..., "dtype": ...}) or return as-is."""
    if isinstance(arr, dict) and "bdata" in arr:
        raw = base64.b64decode(arr["bdata"])
        fmt = {"f8": "d", "f4": "f", "i8": "q", "i4": "i", "u8": "Q", "u4": "I"}[
            arr.get("dtype", "f8")
        ]
        return list(struct.unpack(f"<{len(raw) // struct.calcsize(fmt)}{fmt}", raw))
    return list(arr)  # type: ignore[arg-type]


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed figure payloads (patched without a full re-run) must agree
    with the numbers in their own traces."""
    figures = Path(__file__).parents[1] / "reports" / "figures"

    gap = json.loads((figures / "gap_pct.json").read_text())
    title = gap["layout"]["title"]["text"]
    alns_y = _decode(next(t for t in gap["data"] if t["name"] == "alns")["y"])
    n_under = sum(1 for v in alns_y if v < -0.005)
    assert f"{n_under} runs undercut best-known distance" in title
    assert f"{n_under} ALNS results undercut best-known references" in title
    iqrs = {}
    for t in gap["data"]:
        q = statistics.quantiles(_decode(t["y"]), n=4)
        iqrs[t["name"]] = q[2] - q[0]
    assert iqrs["alns"] <= min(iqrs.values())  # "tightest gap distribution"

    profile = json.loads((figures / "solver_profile.json").read_text())
    title = profile["layout"]["title"]["text"]
    per_inst: dict[str, dict[str, float]] = {}
    for t in profile["data"]:
        for inst, dist in zip(_decode(t["customdata"]), _decode(t["y"]), strict=True):
            per_inst.setdefault(inst[0], {})[t["name"]] = dist
    n_best = sum(1 for s in per_inst.values() if s["alns"] == min(s.values()))
    winners = {min(s, key=s.get) for s in per_inst.values() if s["alns"] != min(s.values())}
    assert f"shortest routes on {n_best} of {len(per_inst)} instances" in title
    assert winners == {"alns_fleet"}
    assert f"alns_fleet takes the other {len(per_inst) - n_best}" in title

    fam = json.loads((figures / "family_gap.json").read_text())
    title = fam["layout"]["title"]["text"]
    traces = {(t["name"], t.get("yaxis", "y")): t for t in fam["data"]}
    gap_y = dict(
        zip(_decode(traces[("alns", "y")]["x"]), _decode(traces[("alns", "y")]["y"]), strict=True)
    )
    veh_y = dict(
        zip(
            _decode(traces[("alns", "y2")]["x"]),
            _decode(traces[("alns", "y2")]["y"]),
            strict=True,
        )
    )
    worst_family = max(gap_y, key=gap_y.get)
    assert f"worst gap {gap_y[worst_family]:.2f}% ({worst_family})" in title
    assert veh_y["C1"] == veh_y["C2"]
    assert f"+{veh_y['C1']:.0f} vehicle in clustered families" in title
    assert f"up to +{max(veh_y['R2'], veh_y['RC2']):.1f} in R2/RC2" in title

    pareto = json.loads((figures / "pareto_gap_runtime.json").read_text())
    title = pareto["layout"]["title"]["text"]
    near = {
        t["name"]
        for t in pareto["data"]
        if 3.0 <= _decode(t["y"])[0] <= 5.0 and 0.5 <= _decode(t["x"])[0] <= 2.0
    }
    assert near == {"alns", "alns_fleet"}
    assert "The ALNS arms are the only solvers near a 4% gap at about 1 s" in title

    eda = json.loads((figures / "eda_instance_map.json").read_text())
    title = eda["layout"]["title"]["text"]
    customers = next(t for t in eda["data"] if t["name"] == "customers")
    widths = _decode(customers["marker"]["color"])
    span = f"vary {min(widths):.0f}\u2013{max(widths):.0f} units across {len(widths)} customers"
    assert span in title
