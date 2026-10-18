"""Evaluation pipeline orchestration for the routing-optimization showcase.

Downloads/solves/evaluates are staged by the CLI and ``dvc.yaml``; this module
holds the orchestration (data-quality gates, timed solver runs, the two seeded
HPO stages, artifact persistence) and re-exports the figure builders
(:mod:`routing_optimization.figures`) and markdown reporters
(:mod:`routing_optimization.reporting`) for convenience and backward
compatibility.
"""

import csv
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import polars as pl
import yaml  # type: ignore[import-untyped]
from portfolio_core.dq import DQReport
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json
from portfolio_eval.report import EvalReport

from routing_optimization.config import VRPConfig
from routing_optimization.construct import (
    clarke_wright_savings,
    nearest_neighbor,
    randomized,
)
from routing_optimization.figures import (
    AlnsConvergenceHistory,
    alns_convergence_figure,
    convergence_figure,
    eda_instance_map_figure,
    family_gap_figure,
    gap_figure,
    pareto_figure,
    route_map_figure,
    runtime_figure,
    solver_profile_figure,
)
from routing_optimization.ortools_solver import ortools_cp
from routing_optimization.parser import parse_solomon_file
from routing_optimization.reporting import (
    family_markdown,
    family_of,
    gap_pct,
    results_markdown,
    summary_markdown,
)
from routing_optimization.schemas import AlnsTuning, Problem, RoutePlan, TwoOptTuning
from routing_optimization.solver import alns, two_opt
from routing_optimization.tuning import best_start, restart_plans, run_alns_hpo, run_hpo

logger = get_logger(__name__)

TWO_OPT_LABEL = "two_opt"


@dataclass(frozen=True)
class SolverRun:
    """One solver's outcome on one instance."""

    solver: str
    total_distance: float
    n_vehicles: int
    runtime_s: float
    base_solver: str | None = None


@dataclass
class InstanceEvaluation:
    """All solver outcomes for one instance plus best-known reference."""

    instance: str
    n_customers: int
    vehicle_capacity: float
    best_known: float | None
    best_known_vehicles: int | None = None
    runs: list[SolverRun] = field(default_factory=list)
    best_routes: list[list[int]] | None = None

    def best(self) -> SolverRun:
        """The cheapest solver run."""
        return min(self.runs, key=lambda r: r.total_distance)

    def best_by_benchmark_convention(self) -> SolverRun:
        """Best run under the Solomon ranking: vehicles first, then distance."""
        return min(self.runs, key=lambda r: (r.n_vehicles, r.total_distance))


def canonical_instance_name(raw: str) -> str:
    """Normalize instance names: ``C1_01``/``c101.txt``/``rc108`` -> ``C101``/``RC108``."""
    stem = Path(raw.strip()).stem
    return stem.upper().replace("_", "")


def load_references(path: Path, supplement_path: Path | None = None) -> dict[str, "Reference"]:
    """Load best-known distance AND vehicle count per instance.

    Vehicle count is the Solomon benchmark's primary ranking criterion
    (SINTEF hierarchical objective), distance the tie-breaker. Rows with an
    empty vehicle field yield ``Reference.vehicles=None`` (distance-only
    comparison for those instances).
    """
    table: dict[str, Reference] = {}

    def _merge(source: Path) -> None:
        with source.open(newline="", encoding="utf-8") as fh:
            rows = (ln for ln in csv.reader(fh) if ln and not ln[0].strip().startswith("#"))
            for row in rows:
                if len(row) < 2 or not row[0].strip():
                    continue
                try:
                    distance = float(row[1])
                except ValueError:
                    continue  # header row or non-numeric reference value
                vehicles: int | None = None
                if len(row) >= 3 and row[2].strip():
                    try:
                        vehicles = int(row[2])
                    except ValueError:
                        vehicles = None
                table.setdefault(canonical_instance_name(row[0]), Reference(distance, vehicles))

    _merge(path)
    if supplement_path is not None and supplement_path.exists():
        _merge(supplement_path)
    return table


def load_best_known(path: Path, supplement_path: Path | None = None) -> dict[str, float]:
    """Distance-only view of :func:`load_references` (backward-compatible)."""
    return {name: ref.distance for name, ref in load_references(path, supplement_path).items()}


@dataclass(frozen=True)
class Reference:
    """Published best-known solution for one instance."""

    distance: float
    vehicles: int | None = None


def _alns_checkpoints(
    trace: list[float], stats: dict[str, list[list[float]]], n_checkpoints: int = 6
) -> AlnsConvergenceHistory:
    """Sample the per-iteration ALNS best-distance trace at ~``n_checkpoints``
    evenly spaced checkpoints, plus the destroy-operator weights per adapted
    segment — the inputs of the ``alns_convergence`` figure."""
    n = len(trace)
    if n <= n_checkpoints:
        idx = list(range(n))
    else:
        step = (n - 1) / (n_checkpoints - 1)
        idx = sorted({round(i * step) for i in range(n_checkpoints)})
    weights = stats.get("destroy_weights", [])
    return {
        "iterations": [float(i) for i in idx],
        "best": [trace[i] for i in idx],
        "segments": [float(k + 1) for k in range(len(weights))],
        "destroy_weights": [list(w) for w in weights],
    }


def run_dq(problem: Problem) -> DQReport:
    """Data-quality gates for one parsed instance; failures halt the pipeline."""
    report = DQReport(dataset=problem.name, n_rows=len(problem.customers))
    demands = [c.demand for c in problem.customers]
    xs = [c.x for c in problem.customers]
    ys = [c.y for c in problem.customers]
    dues = [c.due_time for c in problem.customers]
    report.check_null_rate("demand", 0.0, 0.0)
    report.check_range("demand", min(demands), max(demands), 0.0, problem.vehicle_capacity)
    report.check_range("x", min(xs), max(xs), -1000.0, 1000.0)
    report.check_range("y", min(ys), max(ys), -1000.0, 1000.0)
    report.check_range("due_time", min(dues), max(dues), 0.0, max(dues))
    return report


def solve_instance(problem: Problem, max_iterations: int, seed: int = 42) -> dict[str, RoutePlan]:
    """Run all four solvers; 2-opt polishes the better construction heuristic."""
    nn = nearest_neighbor(problem)
    cw = clarke_wright_savings(problem)
    rnd = randomized(problem, seed=seed)
    base = min((nn, cw), key=lambda p: p.total_distance)
    opt = two_opt(problem, base, max_iterations=max_iterations)
    return {
        "nearest_neighbor": nn,
        "clarke_wright": cw,
        "randomized": rnd,
        TWO_OPT_LABEL: opt,
    }


def solve_with_timing(
    problem: Problem, max_iterations: int, seed: int = 42
) -> tuple[list[SolverRun], dict[str, RoutePlan]]:
    """Run all four solvers on ``problem``, timing each one."""
    runs: list[SolverRun] = []
    plans: dict[str, RoutePlan] = {}
    constructors = (
        ("nearest_neighbor", nearest_neighbor),
        ("clarke_wright", clarke_wright_savings),
    )
    for name, fn in constructors:
        t0 = time.perf_counter()
        plan = fn(problem)
        runs.append(SolverRun(name, plan.total_distance, plan.n_vehicles, time.perf_counter() - t0))
        plans[name] = plan

    t0 = time.perf_counter()
    rnd = randomized(problem, seed=seed)
    runs.append(
        SolverRun("randomized", rnd.total_distance, rnd.n_vehicles, time.perf_counter() - t0)
    )
    plans["randomized"] = rnd

    base_name = min(("nearest_neighbor", "clarke_wright"), key=lambda k: plans[k].total_distance)
    t0 = time.perf_counter()
    improved = two_opt(problem, plans[base_name], max_iterations=max_iterations)
    runs.append(
        SolverRun(
            TWO_OPT_LABEL,
            improved.total_distance,
            improved.n_vehicles,
            time.perf_counter() - t0,
            base_solver=base_name,
        )
    )
    plans[TWO_OPT_LABEL] = improved
    return runs, plans


def evaluate_instance(
    problem: Problem, max_iterations: int, best_known: float | None, seed: int = 42
) -> InstanceEvaluation:
    """Solve one instance and attach the best-known reference distance."""
    evaln = InstanceEvaluation(
        instance=canonical_instance_name(problem.name),
        n_customers=problem.n_customers,
        vehicle_capacity=problem.vehicle_capacity,
        best_known=best_known,
    )
    evaln.runs, plans = solve_with_timing(problem, max_iterations, seed=seed)
    evaln.best_routes = plans[evaln.best().solver].routes
    return evaln


def run_solve(cfg: VRPConfig) -> Path:
    """Solve every configured instance and persist ``reports/solutions.json``.

    Runs the four base solvers, then the seeded HPO over the improvement
    stage, then one ``two_opt_tuned`` run per instance with the chosen
    configuration. The chosen config is persisted to ``params.yaml`` under
    ``solver_best`` (idempotent: identical across runs for a fixed seed).
    """
    payload: dict[str, object] = {
        "seed": cfg.seed,
        "max_two_opt_iterations": cfg.max_two_opt_iterations,
        "instances": {},
    }
    dq_doc = ["# Data-quality gates — Solomon VRPTW subset", ""]
    instances_payload: dict[str, object] = {}
    problems: list[Problem] = []
    runs_by_inst: dict[str, list[SolverRun]] = {}
    plans_by_inst: dict[str, dict[str, RoutePlan]] = {}

    for inst in cfg.instances:
        path = cfg.raw_dir / f"{inst}.txt"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing — run `routing_optimization download` first")
        problem = parse_solomon_file(path, name=inst)
        dq = run_dq(problem)
        dq.raise_if_failed()
        dq_doc += [f"## {inst}", "", dq.to_markdown(), ""]
        problems.append(problem)
        runs, plans = solve_with_timing(problem, cfg.max_two_opt_iterations, seed=cfg.seed)
        runs_by_inst[inst] = runs
        plans_by_inst[inst] = plans

    bases = {
        inst: min(
            (plans["nearest_neighbor"], plans["clarke_wright"]),
            key=lambda p: p.total_distance,
        )
        for inst, plans in plans_by_inst.items()
    }
    hpo = run_hpo(problems, bases, cfg)

    # Tuned 2-opt runs (also the ALNS starting points).
    convergence: dict[str, dict[str, list[float]]] = {}
    alns_convergence: dict[str, AlnsConvergenceHistory] = {}
    for problem in problems:
        inst = problem.name
        runs = runs_by_inst[inst]
        plans = plans_by_inst[inst]
        restarts = restart_plans(problem, seed=cfg.seed, restarts=hpo.tuning.restarts)
        start = best_start(bases[inst], restarts)
        trace: list[float] | None = [] if inst in cfg.convergence_instances else None
        t0 = time.perf_counter()
        tuned = two_opt(
            problem,
            start,
            max_iterations=hpo.tuning.max_iterations,
            acceptance=hpo.tuning.acceptance,
            tail_exchange=hpo.tuning.tail_exchange,
            trace=trace,
        )
        tuned_runtime = time.perf_counter() - t0
        runs.append(
            SolverRun(
                "two_opt_tuned",
                tuned.total_distance,
                tuned.n_vehicles,
                tuned_runtime,
                base_solver=f"{start.solver} best-of-{hpo.tuning.restarts}",
            )
        )
        plans["two_opt_tuned"] = tuned
        if trace is not None:
            untuned_trace: list[float] = []
            two_opt(
                problem,
                bases[inst],
                max_iterations=cfg.max_two_opt_iterations,
                trace=untuned_trace,
            )
            convergence[inst] = {"untuned": untuned_trace, "tuned": trace}

    # ALNS knob search on the representative subset, then ALNS on every instance.
    problem_by_name = {p.name: p for p in problems}
    tuned_starts = {inst: plans["two_opt_tuned"] for inst, plans in plans_by_inst.items()}
    alns_hpo = run_alns_hpo(problem_by_name, tuned_starts, cfg)

    for problem in problems:
        inst = problem.name
        runs = runs_by_inst[inst]
        plans = plans_by_inst[inst]
        alns_trace: list[float] | None = [] if inst in cfg.convergence_instances else None
        stats: dict[str, list[list[float]]] | None = {} if alns_trace is not None else None
        t0 = time.perf_counter()
        plan = alns(
            problem,
            start=tuned_starts[inst],
            seed=cfg.seed,
            max_iterations=cfg.alns_max_iterations,
            segment_length=alns_hpo.tuning.segment_length,
            reaction_factor=alns_hpo.tuning.reaction_factor,
            init_weights=alns_hpo.tuning.init_weights,
            destroy_q=cfg.alns_destroy_q,
            trace=alns_trace,
            stats=stats,
        )
        alns_runtime = time.perf_counter() - t0
        runs.append(
            SolverRun(
                "alns",
                plan.total_distance,
                plan.n_vehicles,
                alns_runtime,
                base_solver="two_opt_tuned",
            )
        )
        plans["alns"] = plan
        if alns_trace is not None:
            alns_convergence[inst] = _alns_checkpoints(alns_trace, stats or {})

        # Hinted cross-check: time-bounded CP-SAT with the ALNS plan as the
        # hint, so a feasible incumbent exists from the first millisecond.
        # This is an incumbent-improvement probe, not an independent baseline
        # (the plan is returned unchanged on timeout); the asymmetry is
        # disclosed in README/story.
        t0 = time.perf_counter()
        cp_plan = ortools_cp(
            problem,
            hint=plan,
            time_limit_s=cfg.ortools_time_limit_s,
            max_vehicles=cfg.ortools_max_vehicles,
            fleet_slack=cfg.ortools_fleet_slack,
            seed=cfg.seed,
        )
        runs.append(
            SolverRun(
                "ortools_cp",
                cp_plan.total_distance,
                cp_plan.n_vehicles,
                time.perf_counter() - t0,
                base_solver="alns",
            )
        )
        plans["ortools_cp"] = cp_plan

        best = min(runs, key=lambda r: r.total_distance)
        instances_payload[inst] = {
            "n_customers": problem.n_customers,
            "vehicle_capacity": problem.vehicle_capacity,
            "max_vehicles": problem.max_vehicles,
            "solvers": {
                r.solver: {
                    "total_distance": round(r.total_distance, 4),
                    "n_vehicles": r.n_vehicles,
                    "runtime_s": round(r.runtime_s, 6),
                    **({"base_solver": r.base_solver} if r.base_solver else {}),
                }
                for r in runs
            },
            "best": {
                "solver": best.solver,
                "total_distance": round(best.total_distance, 4),
                "n_vehicles": best.n_vehicles,
                "routes": plans[best.solver].routes,
            },
        }
        logger.info(
            "%s best=%s distance=%.2f vehicles=%d",
            inst,
            best.solver,
            best.total_distance,
            best.n_vehicles,
        )

    payload["instances"] = instances_payload
    payload["solver_best"] = hpo.tuning.model_dump()
    payload["hpo"] = {
        "trials": len(hpo.trials),
        "best_mean_distance": round(hpo.best.mean_distance, 4),
    }
    payload["alns_best"] = alns_hpo.tuning.model_dump()
    payload["alns_hpo"] = {
        "trials": len(alns_hpo.trials),
        "subset": [n for n in cfg.alns_hpo_instances if n in tuned_starts],
        "best_mean_distance": round(alns_hpo.best.mean_distance, 4),
    }
    payload["convergence"] = convergence
    payload["alns_convergence"] = alns_convergence
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    solutions_path = cfg.reports_dir / "solutions.json"
    solutions_path.write_text(json.dumps(payload, indent=2))
    (cfg.reports_dir / "dq.md").write_text("\n".join(dq_doc))
    persist_solver_best(cfg, hpo.tuning, alns_hpo.tuning)
    return solutions_path


def persist_solver_best(cfg: VRPConfig, tuning: TwoOptTuning, alns_tuning: AlnsTuning) -> Path:
    """Write the chosen configs to ``params.yaml`` (idempotent).

    Replaces only the ``solver_best:`` / ``alns_best:`` blocks (or appends
    them), preserving the rest of the file — including comments — byte for
    byte. Tests override the target via ``cfg.params_path``.
    """
    params_path = cfg.params_path or Path(__file__).resolve().parents[2] / "params.yaml"
    text = params_path.read_text() if params_path.exists() else ""

    def replace_block(source: str, key: str, block: str) -> str:
        head, sep, _tail = source.partition(f"{key}:\n")
        if sep:
            return head + block
        return source + ("\n" if source and not source.endswith("\n") else "") + block

    text = replace_block(
        text, "solver_best", "solver_best:\n" + yaml.safe_dump(tuning.model_dump(), sort_keys=False)
    )
    text = replace_block(
        text,
        "alns_best",
        "alns_best:\n" + yaml.safe_dump(alns_tuning.model_dump(), sort_keys=False),
    )
    params_path.write_text(text)
    logger.info("persisted to %s: %s | %s", params_path, tuning.summary(), alns_tuning.summary())
    return params_path


def _solver_gaps(evaln: InstanceEvaluation) -> dict[str, float | None]:
    """Gap per solver run; None when no best-known reference exists."""
    gaps: dict[str, float | None] = {}
    for r in evaln.runs:
        gaps[r.solver] = (
            None if evaln.best_known is None else gap_pct(r.total_distance, evaln.best_known)
        )
    return gaps


@dataclass(frozen=True)
class GapTables:
    """Per-run Polars frames feeding the gap, runtime and profile figures."""

    gap_rows: pl.DataFrame
    runtime_rows: pl.DataFrame
    distance_rows: pl.DataFrame


@dataclass(frozen=True)
class SolverStats:
    """Mean gap/runtime/vehicle aggregates for one solver across instances."""

    mean_gap_pct: float
    mean_runtime_s: float
    mean_n_vehicles: float
    mean_veh_delta: float


@dataclass(frozen=True)
class MarkdownReports:
    """The three markdown sections shared by ``results.md`` and ``report.html``."""

    detail: str
    summary: str
    family: str


def _load_evaluations(
    solutions: dict[str, Any], references: dict[str, "Reference"]
) -> list[InstanceEvaluation]:
    """Rehydrate typed per-instance evaluations from ``solutions.json`` runs."""
    evaluations: list[InstanceEvaluation] = []
    for inst, data in solutions["instances"].items():
        solvers = [
            SolverRun(
                solver=name,
                total_distance=float(res["total_distance"]),
                n_vehicles=int(res["n_vehicles"]),
                runtime_s=float(res["runtime_s"]),
                base_solver=res.get("base_solver"),
            )
            for name, res in data["solvers"].items()
        ]
        ref = references.get(canonical_instance_name(inst))
        evaluations.append(
            InstanceEvaluation(
                instance=inst,
                n_customers=int(data["n_customers"]),
                vehicle_capacity=float(data["vehicle_capacity"]),
                best_known=ref.distance if ref else None,
                best_known_vehicles=ref.vehicles if ref else None,
                runs=solvers,
                best_routes=data["best"]["routes"],
            )
        )
    return evaluations


def _gap_tables(evaluations: list[InstanceEvaluation]) -> GapTables:
    """Per-run frames: gaps (reference-gated), runtimes and distances."""
    gap_rows = pl.DataFrame(
        {
            "instance": ev.instance,
            "solver": r.solver,
            "gap_pct": round(gap_pct(r.total_distance, ev.best_known), 4),
        }
        for ev in evaluations
        if ev.best_known is not None
        for r in ev.runs
    )
    runtime_rows = pl.DataFrame(
        {"instance": ev.instance, "solver": r.solver, "runtime_s": max(r.runtime_s, 1e-6)}
        for ev in evaluations
        for r in ev.runs
    )
    distance_rows = pl.DataFrame(
        {"instance": ev.instance, "solver": r.solver, "distance": r.total_distance}
        for ev in evaluations
        for r in ev.runs
    )
    return GapTables(gap_rows=gap_rows, runtime_rows=runtime_rows, distance_rows=distance_rows)


def _family_rows(evaluations: list[InstanceEvaluation]) -> pl.DataFrame:
    """Per (family, solver) gap and vehicle-delta frame for the family figure."""
    return pl.DataFrame(
        {
            "family": family_of(ev.instance),
            "solver": r.solver,
            "gap_pct": round(gap_pct(r.total_distance, ev.best_known), 4),
            "veh_delta": (
                r.n_vehicles - ev.best_known_vehicles
                if ev.best_known_vehicles is not None
                else None
            ),
        }
        for ev in evaluations
        if ev.best_known is not None
        for r in ev.runs
    )


def _one_solver_stats(evaluations: list[InstanceEvaluation], solver: str) -> SolverStats:
    """Mean aggregates of one solver; reference-gated means over the gated rows only."""
    runs = [(ev, r) for ev in evaluations for r in ev.runs if r.solver == solver]
    n = max(len(runs), 1)
    gap_vals = [
        gap_pct(r.total_distance, ev.best_known) for ev, r in runs if ev.best_known is not None
    ]
    veh_deltas = [
        r.n_vehicles - ev.best_known_vehicles
        for ev, r in runs
        if ev.best_known_vehicles is not None
    ]
    return SolverStats(
        mean_gap_pct=sum(gap_vals) / max(len(gap_vals), 1),
        mean_runtime_s=sum(r.runtime_s for _ev, r in runs) / n,
        mean_n_vehicles=sum(r.n_vehicles for _ev, r in runs) / n,
        mean_veh_delta=sum(veh_deltas) / max(len(veh_deltas), 1),
    )


def _solver_stats(evaluations: list[InstanceEvaluation]) -> dict[str, SolverStats]:
    """Mean aggregates for every solver, keyed in sorted-solver order."""
    solvers = sorted({r.solver for ev in evaluations for r in ev.runs})
    return {solver: _one_solver_stats(evaluations, solver) for solver in solvers}


def _pareto_rows(stats: dict[str, SolverStats]) -> pl.DataFrame:
    """One unrounded row per solver: mean runtime, gap and vehicle delta."""
    return pl.DataFrame(
        {
            "solver": solver,
            "mean_runtime_s": s.mean_runtime_s,
            "mean_gap_pct": s.mean_gap_pct,
            "mean_veh_delta": s.mean_veh_delta,
        }
        for solver, s in stats.items()
    )


def _convergence_figures(solutions: dict[str, Any]) -> dict[str, go.Figure]:
    """2-opt convergence figures for every traced instance."""
    return {
        f"convergence_{inst}": convergence_figure(history, inst)
        for inst, history in solutions.get("convergence", {}).items()
    }


def _alns_convergence_figures(solutions: dict[str, Any]) -> dict[str, go.Figure]:
    """ALNS convergence figures for every traced instance."""
    return {
        f"alns_convergence_{inst}": alns_convergence_figure(history, inst)
        for inst, history in solutions.get("alns_convergence", {}).items()
    }


def _map_figures(cfg: VRPConfig, evaluations: list[InstanceEvaluation]) -> dict[str, go.Figure]:
    """EDA instance map plus the best-route map for the configured instance."""
    map_eval = next((ev for ev in evaluations if ev.instance == cfg.map_instance), evaluations[0])
    map_problem = parse_solomon_file(
        cfg.raw_dir / f"{map_eval.instance}.txt", name=map_eval.instance
    )
    figures = {"eda_instance_map": eda_instance_map_figure(map_problem)}
    if map_eval.best_routes is not None:
        best = map_eval.best()
        gap = (
            f" — within {gap_pct(best.total_distance, map_eval.best_known):.2f}% of best-known"
            if map_eval.best_known is not None
            else ""
        )
        figures[f"route_map_{map_eval.instance}"] = route_map_figure(
            map_problem,
            map_eval.best_routes,
            title=(
                f"ALNS routes all 100 {map_eval.instance} customers feasibly "
                f"(capacity + time windows{gap})"
            ),
        )
    return figures


def _build_figures(
    cfg: VRPConfig,
    evaluations: list[InstanceEvaluation],
    solutions: dict[str, Any],
    tables: GapTables,
    stats: dict[str, SolverStats],
) -> dict[str, go.Figure]:
    """Every figure of the evaluation report, in report-order."""
    figures: dict[str, go.Figure] = {
        "gap_pct": gap_figure(tables.gap_rows),
        "runtime": runtime_figure(tables.runtime_rows),
        "solver_profile": solver_profile_figure(tables.distance_rows),
    }
    figures.update(_convergence_figures(solutions))
    figures.update(_map_figures(cfg, evaluations))
    figures["family_gap"] = family_gap_figure(_family_rows(evaluations))
    figures["pareto_gap_runtime"] = pareto_figure(_pareto_rows(stats))
    figures.update(_alns_convergence_figures(solutions))
    return figures


def _write_figures(figures: dict[str, go.Figure], figures_dir: Path) -> None:
    """Persist figure payloads, dropping stale ones from previous runs."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    # drop stale figure payloads from previous runs (e.g. changed instance lists)
    for stale in figures_dir.iterdir():
        if stale.suffix in {".html", ".json"} and stale.stem not in figures:
            stale.unlink()
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")


def _markdown_reports(evaluations: list[InstanceEvaluation]) -> MarkdownReports:
    """Summary, per-family and per-instance markdown sections."""
    return MarkdownReports(
        detail=results_markdown(evaluations),
        summary=summary_markdown(evaluations),
        family=family_markdown(evaluations),
    )


def _write_results_md(cfg: VRPConfig, reports: MarkdownReports) -> None:
    """Write ``reports/results.md`` from the three markdown sections."""
    (cfg.reports_dir / "results.md").write_text(
        f"# Routing optimization — evaluation results\n\n## Summary (mean over instances)\n\n"
        f"{reports.summary}\n\n## Per-family results\n\n{reports.family}\n\n"
        f"## Per-instance results\n\n{reports.detail}\n"
    )


def _write_report_html(
    cfg: VRPConfig, figures: dict[str, go.Figure], reports: MarkdownReports
) -> None:
    """Write the self-contained HTML report with figure links."""
    report = EvalReport(title="Routing Optimization — Solomon VRPTW benchmark")
    report.add_markdown_table("Summary (mean over instances)", reports.summary)
    report.add_markdown_table("Per-family results", reports.family)
    report.add_markdown_table("Per-instance results", reports.detail)
    for name in figures:
        report.add_html(
            name.replace("_", " ").title(),
            f'<p><a href="figures/{name}.html">interactive figure</a> '
            f"(<code>figures/{name}.html</code>)</p>",
        )
    report.write(cfg.reports_dir / "report.html")


def _summary_metrics(stats: dict[str, SolverStats]) -> dict[str, dict[str, float]]:
    """Rounded per-solver means for the ``summary`` block of ``metrics.json``."""
    return {
        solver: {
            "mean_gap_pct": round(s.mean_gap_pct, 4),
            "mean_runtime_s": round(s.mean_runtime_s, 6),
            "mean_n_vehicles": round(s.mean_n_vehicles, 2),
            "mean_vehicle_delta": round(s.mean_veh_delta, 2),
        }
        for solver, s in stats.items()
    }


def _instance_metrics(evaluations: list[InstanceEvaluation]) -> dict[str, Any]:
    """Per-instance best solver, gaps, vehicle deltas and per-solver detail."""
    return {
        ev.instance: {
            "best_known": ev.best_known,
            "best_known_vehicles": ev.best_known_vehicles,
            "best_solver": ev.best().solver,
            "best_solver_benchmark_convention": ev.best_by_benchmark_convention().solver,
            "best_distance": round(ev.best().total_distance, 4),
            "best_gap_pct": (
                None
                if ev.best_known is None
                else round(gap_pct(ev.best().total_distance, ev.best_known), 4)
            ),
            "solvers": {
                r.solver: {
                    "distance": round(r.total_distance, 4),
                    "n_vehicles": r.n_vehicles,
                    "gap_pct": (
                        None
                        if ev.best_known is None
                        else round(gap_pct(r.total_distance, ev.best_known), 4)
                    ),
                    "vehicle_delta": (
                        None
                        if ev.best_known_vehicles is None
                        else r.n_vehicles - ev.best_known_vehicles
                    ),
                    "runtime_s": round(r.runtime_s, 6),
                }
                for r in ev.runs
            },
        }
        for ev in evaluations
    }


def _ranking_counts(
    evaluations: list[InstanceEvaluation], key: Callable[[InstanceEvaluation], str]
) -> dict[str, int]:
    """Win count per solver under ``key`` (best-known-gated), sorted by solver."""
    return dict(
        sorted(
            {
                solver: sum(
                    1 for ev in evaluations if key(ev) == solver and ev.best_known is not None
                )
                for solver in {r.solver for ev in evaluations for r in ev.runs}
            }.items()
        )
    )


def _ranking_metrics(evaluations: list[InstanceEvaluation]) -> dict[str, Any]:
    """Instance-win rankings by cheapest run and by benchmark convention."""
    return {
        "by_distance": _ranking_counts(evaluations, lambda ev: ev.best().solver),
        "by_vehicles_then_distance": _ranking_counts(
            evaluations, lambda ev: ev.best_by_benchmark_convention().solver
        ),
    }


def _family_solver_mean(
    evaluations: list[InstanceEvaluation], fam: str, solver: str, *, vehicles: bool
) -> float:
    """Mean gap (or vehicle delta) of ``solver`` on family ``fam``.

    Gap means are gated on instances with a best-known distance, vehicle-delta
    means on instances with a best-known vehicle count; empty sets average to 0.
    """
    vals: list[float] = []
    for ev in evaluations:
        if family_of(ev.instance) != fam:
            continue
        if vehicles:
            if ev.best_known_vehicles is None:
                continue
        elif ev.best_known is None:
            continue
        for r in ev.runs:
            if r.solver != solver:
                continue
            value = (
                None
                if (known := ev.best_known_vehicles if vehicles else ev.best_known) is None
                else r.n_vehicles - known
                if vehicles
                else gap_pct(r.total_distance, known)
            )
            if value is not None:
                vals.append(value)
    return round(sum(vals) / max(len(vals), 1), 2 if vehicles else 4)


def _family_metrics(
    evaluations: list[InstanceEvaluation], *, vehicles: bool
) -> dict[str, dict[str, float]]:
    """Per-family per-solver means (gaps or vehicle deltas), sorted keys."""
    fams = sorted({family_of(ev.instance) for ev in evaluations})
    solvers = sorted({r.solver for ev in evaluations for r in ev.runs})
    return {
        fam: {
            solver: _family_solver_mean(evaluations, fam, solver, vehicles=vehicles)
            for solver in solvers
        }
        for fam in fams
    }


def _metrics_payload(
    evaluations: list[InstanceEvaluation],
    solutions: dict[str, Any],
    stats: dict[str, SolverStats],
) -> dict[str, Any]:
    """Assemble the ``metrics.json`` document (keys in write order)."""
    return {
        "summary": _summary_metrics(stats),
        "instances": _instance_metrics(evaluations),
        "ranking": _ranking_metrics(evaluations),
        "tuning": {
            "solver_best": solutions.get("solver_best"),
            "hpo": solutions.get("hpo"),
            "alns_best": solutions.get("alns_best"),
            "alns_hpo": solutions.get("alns_hpo"),
        },
        "families": _family_metrics(evaluations, vehicles=False),
        "family_vehicle_deltas": _family_metrics(evaluations, vehicles=True),
    }


def run_evaluate(cfg: VRPConfig) -> Path:
    """Compute gaps, build figures and write all evaluation artifacts."""
    solutions_path = cfg.reports_dir / "solutions.json"
    if not solutions_path.exists():
        raise FileNotFoundError(
            f"{solutions_path} missing — run `routing_optimization solve` first"
        )
    solutions = json.loads(solutions_path.read_text())
    references = load_references(cfg.best_known_path, cfg.best_known_supplement_path)
    evaluations = _load_evaluations(solutions, references)

    tables = _gap_tables(evaluations)
    stats = _solver_stats(evaluations)
    figures = _build_figures(cfg, evaluations, solutions, tables, stats)
    _write_figures(figures, cfg.reports_dir / "figures")
    reports = _markdown_reports(evaluations)
    _write_results_md(cfg, reports)
    metrics = _metrics_payload(evaluations, solutions, stats)
    metrics_path = cfg.reports_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    _write_report_html(cfg, figures, reports)
    return metrics_path


__all__ = [
    "InstanceEvaluation",
    "SolverRun",
    "alns_convergence_figure",
    "canonical_instance_name",
    "convergence_figure",
    "eda_instance_map_figure",
    "evaluate_instance",
    "family_gap_figure",
    "family_markdown",
    "family_of",
    "gap_figure",
    "gap_pct",
    "load_best_known",
    "pareto_figure",
    "persist_solver_best",
    "results_markdown",
    "route_map_figure",
    "run_dq",
    "run_evaluate",
    "run_solve",
    "runtime_figure",
    "solve_instance",
    "solve_with_timing",
    "solver_profile_figure",
    "summary_markdown",
]
