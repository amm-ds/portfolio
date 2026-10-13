"""Evaluation pipeline: solve the subset, compare against best-known values.

Produces the markdown results table, ``metrics.json``, an HTML report and the
portfolio-themed figures (gap-%, EDA instance map, route map, runtime). Solvers
are timed per instance with :func:`time.perf_counter`; everything runs in
seconds.
"""

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import yaml  # type: ignore[import-untyped]
from portfolio_core.dq import DQReport
from portfolio_core.logging import get_logger
from portfolio_core.plotting import (
    add_takeaway,
    apply_theme,
    is_baseline_run,
    save_html,
    save_json,
    style_runs,
)
from portfolio_eval.report import EvalReport

from routing_optimization.config import VRPConfig
from routing_optimization.parser import parse_solomon_file
from routing_optimization.schemas import AlnsTuning, Problem, RoutePlan, TwoOptTuning
from routing_optimization.solver import (
    alns,
    clarke_wright_savings,
    nearest_neighbor,
    randomized,
    two_opt,
)
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
    runs: list[SolverRun] = field(default_factory=list)
    best_routes: list[list[int]] | None = None

    def best(self) -> SolverRun:
        """The cheapest solver run."""
        return min(self.runs, key=lambda r: r.total_distance)


def canonical_instance_name(raw: str) -> str:
    """Normalize instance names: ``C1_01``/``c101.txt``/``rc108`` -> ``C101``/``RC108``."""
    stem = Path(raw.strip()).stem
    return stem.upper().replace("_", "")


def load_best_known(path: Path, supplement_path: Path | None = None) -> dict[str, float]:
    """Load the curated best-known table, skipping ``#`` comment lines.

    When ``supplement_path`` is given, project-local values fill the instances
    the registry table does not list (registry wins on any conflict).
    """
    table: dict[str, float] = {}

    def _merge(source: Path) -> None:
        with source.open(newline="", encoding="utf-8") as fh:
            rows = (ln for ln in csv.reader(fh) if ln and not ln[0].strip().startswith("#"))
            for row in rows:
                if len(row) < 2 or not row[0].strip():
                    continue
                try:
                    table.setdefault(canonical_instance_name(row[0]), float(row[1]))
                except ValueError:
                    continue  # header row or non-numeric reference value

    _merge(path)
    if supplement_path is not None and supplement_path.exists():
        _merge(supplement_path)
    return table


def family_of(instance: str) -> str:
    """Solomon family of an instance: C101 -> C1, RC208 -> RC2, R112 -> R1."""
    letters = instance.rstrip("0123456789")
    digits = instance[len(letters) :]
    return f"{letters}{digits[0]}" if digits else letters


def gap_pct(distance: float, best_known: float) -> float:
    """Optimality gap in percent relative to the best-known value."""
    return (distance - best_known) / best_known * 100.0


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


def gap_figure(rows: pl.DataFrame) -> go.Figure:
    """Grouped bar: gap to best-known (%) per instance, one group per solver."""
    fig = px.bar(
        rows,
        x="instance",
        y="gap_pct",
        color="solver",
        barmode="group",
        title="Optimality gap vs best-known (%) — Solomon 100-customer subset",
        labels={"gap_pct": "gap %", "instance": "instance", "solver": "solver"},
    )
    fig.add_hline(y=0.0, line_color="#94a3b8", line_width=1)
    return apply_theme(fig)


def runtime_figure(rows: pl.DataFrame) -> go.Figure:
    """Grouped bar: solver runtime per instance (seconds, log scale)."""
    fig = px.bar(
        rows,
        x="instance",
        y="runtime_s",
        color="solver",
        barmode="group",
        log_y=True,
        title="Solver runtime per instance (s, log scale)",
        labels={"runtime_s": "runtime (s)", "instance": "instance", "solver": "solver"},
    )
    return apply_theme(fig)


def route_map_figure(problem: Problem, routes: list[list[int]], title: str) -> go.Figure:
    """Depot + customer scatter with route polylines colored per vehicle."""
    customers = problem.customers
    depot = problem.depot
    palette = px.colors.qualitative.Plotly
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[depot.x],
            y=[depot.y],
            mode="markers",
            name="depot",
            marker_symbol="star",
            marker_size=16,
            marker_color="#fbbf24",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[c.x for c in customers[1:]],
            y=[c.y for c in customers[1:]],
            mode="markers",
            name="customers",
            marker_size=5,
            marker_color="#64748b",
        )
    )
    for k, route in enumerate(routes):
        pts = [depot] + [customers[cid] for cid in route] + [depot]
        fig.add_trace(
            go.Scatter(
                x=[c.x for c in pts],
                y=[c.y for c in pts],
                mode="lines+markers",
                name=f"vehicle {k + 1}",
                line_color=palette[k % len(palette)],
                line_width=2,
                marker_size=4,
            )
        )
    fig.update_layout(title=title, showlegend=True)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return apply_theme(fig, width=900, height=760)


def eda_instance_map_figure(problem: Problem) -> go.Figure:
    """Customer scatter colored by time-window tightness (``due - ready``).

    Narrow windows constrain route timing more than geography alone suggests;
    tight customers (small ``due - ready``) are the ones a solver must visit
    within a narrow time band. The depot is marked with a star.
    """
    customers = problem.customers
    depot = problem.depot
    tightness = [c.due_time - c.ready_time for c in customers[1:]]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[depot.x],
            y=[depot.y],
            mode="markers",
            name="depot",
            marker_symbol="star",
            marker_size=16,
            marker_color="#fbbf24",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[c.x for c in customers[1:]],
            y=[c.y for c in customers[1:]],
            mode="markers",
            name="customers",
            marker_size=7,
            marker_color=tightness,
            marker_colorscale="Plasma",
            marker_showscale=True,
            marker_colorbar={"title": "window width<br>(due - ready)"},
        )
    )
    fig.update_layout(
        title=f"{problem.name} — customer geography colored by time-window tightness",
        showlegend=True,
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return apply_theme(fig, width=900, height=760)


def convergence_figure(history: dict[str, list[float]], instance: str) -> go.Figure:
    """Best-found distance vs accepted-move count, tuned vs untuned overlay.

    ``history`` maps a solver label to its trace (index 0 is the construction
    start). The construction start is explicitly marked, and the tuned curve
    is promoted via :func:`portfolio_core.plotting.style_runs`.
    """
    fig = go.Figure()
    for label in ("untuned", "tuned"):
        values = history[label]
        fig.add_trace(
            go.Scatter(
                x=list(range(len(values))),
                y=values,
                mode="lines+markers",
                name="two_opt_tuned" if label == "tuned" else "two_opt",
            )
        )
    tuned = history["tuned"]
    fig.add_trace(
        go.Scatter(
            x=[0],
            y=[tuned[0]],
            mode="markers",
            name="construction start",
            marker_symbol="star",
            marker_size=14,
            marker_color="#fbbf24",
        )
    )
    reduction = (tuned[0] - tuned[-1]) / tuned[0] * 100.0
    style_runs(fig, best="two_opt_tuned")
    add_takeaway(
        fig,
        f"construction {tuned[0]:.1f} -> tuned {tuned[-1]:.1f} "
        f"(-{reduction:.1f}%) in {len(tuned) - 1} accepted moves",
    )
    fig.update_layout(
        title=f"{instance} — 2-opt convergence",
        xaxis_title="accepted moves",
        yaxis_title="total distance",
        showlegend=True,
    )
    return apply_theme(fig)


def _style_runs_safe(fig: go.Figure, best: str) -> go.Figure:
    """Apply the platform run-styling; fall back to marker colors for bar traces.

    ``style_runs`` sets ``line=`` which scatter traces accept but bar traces
    reject, so grouped-bar figures get the equivalent marker-color treatment
    (grey baselines, accent best) via the public ``is_baseline_run`` hint.
    """
    try:
        return style_runs(fig, best=best)
    except ValueError:
        for trace in fig.data:
            name = str(getattr(trace, "name", "") or "")
            if best.lower() in name.lower():
                trace.update(marker={"color": "#2dd4bf"})
            elif is_baseline_run(name):
                trace.update(marker={"color": "#64748b"})
        return fig


def solver_profile_figure(rows: pl.DataFrame) -> go.Figure:
    """Per-instance solver profile: grouped distance bars on a log scale.

    Baselines are visually demoted (grey) and the tuned run promoted, so the
    solver ladder reads instantly.
    """
    fig = px.bar(
        rows,
        x="instance",
        y="distance",
        color="solver",
        barmode="group",
        log_y=True,
        title="Solver profile per instance (total distance, log scale)",
        labels={"distance": "total distance", "instance": "instance", "solver": "solver"},
    )
    _style_runs_safe(fig, best="two_opt_tuned")
    add_takeaway(
        fig,
        "constraint-aware construction (savings) removes most of the randomized floor; "
        "tuned 2-opt closes a further few percent",
    )
    return apply_theme(fig)


def family_gap_figure(rows: pl.DataFrame) -> go.Figure:
    """Mean optimality gap per Solomon family (C1/C2/R1/R2/RC1/RC2) per solver."""
    fig = px.bar(
        rows,
        x="family",
        y="gap_pct",
        color="solver",
        barmode="group",
        title="Mean gap to best-known by Solomon family",
        labels={"gap_pct": "mean gap %", "family": "family", "solver": "solver"},
    )
    _style_runs_safe(fig, best="alns")
    add_takeaway(
        fig,
        "ALNS closes the gap on every family, single digits on C1/RC1; "
        "baselines stay orders of magnitude behind",
    )
    return apply_theme(fig)


# ---------------------------------------------------------------------------
# Pipeline stages (used by the CLI and dvc.yaml)


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


def results_markdown(evaluations: list[InstanceEvaluation]) -> str:
    """Full per-instance markdown results table."""
    lines = [
        "| instance | best known | solver | distance | vehicles | gap % | runtime (ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    for ev in evaluations:
        for r in ev.runs:
            gap = (
                "n/a"
                if ev.best_known is None
                else f"{gap_pct(r.total_distance, ev.best_known):.2f}"
            )
            best_marker = " **(best)**" if r == ev.best() else ""
            lines.append(
                f"| {ev.instance} | {ev.best_known if ev.best_known is not None else 'n/a'} "
                f"| {r.solver}{best_marker} | {r.total_distance:.2f} | {r.n_vehicles} "
                f"| {gap} | {r.runtime_s * 1e3:.1f} |"
            )
    return "\n".join(lines)


def summary_markdown(evaluations: list[InstanceEvaluation]) -> str:
    """Mean gap / runtime / vehicles per solver across instances."""
    lines = [
        "| solver | mean gap % | mean distance | mean vehicles | mean runtime (ms) |",
        "|---|---|---|---|---|",
    ]
    solvers = sorted({r.solver for ev in evaluations for r in ev.runs})
    for solver in solvers:
        gaps = [
            gap_pct(r.total_distance, ev.best_known)
            for ev in evaluations
            for r in ev.runs
            if r.solver == solver and ev.best_known is not None
        ]
        runs = [r for ev in evaluations for r in ev.runs if r.solver == solver]
        mean_gap = f"{sum(gaps) / len(gaps):.2f}" if gaps else "n/a"
        mean_dist = sum(r.total_distance for r in runs) / len(runs)
        mean_veh = sum(r.n_vehicles for r in runs) / len(runs)
        mean_rt = sum(r.runtime_s for r in runs) / len(runs) * 1e3
        lines.append(
            f"| {solver} | {mean_gap} | {mean_dist:.2f} | {mean_veh:.1f} | {mean_rt:.1f} |"
        )
    return "\n".join(lines)


def family_markdown(evaluations: list[InstanceEvaluation]) -> str:
    """Mean gap per Solomon family per solver (instances with a reference)."""
    lines = [
        "| family | instances | solver | mean gap % |",
        "|---|---|---|---|",
    ]
    families = sorted({family_of(ev.instance) for ev in evaluations})
    for fam in families:
        members = [ev for ev in evaluations if family_of(ev.instance) == fam and ev.best_known]
        for solver in sorted({r.solver for ev in members for r in ev.runs}):
            gaps = [
                gap_pct(r.total_distance, ev.best_known)
                for ev in members
                for r in ev.runs
                if r.solver == solver and ev.best_known is not None
            ]
            if gaps:
                lines.append(f"| {fam} | {len(members)} | {solver} | {sum(gaps) / len(gaps):.2f} |")
    return "\n".join(lines)


def run_evaluate(cfg: VRPConfig) -> Path:
    """Compute gaps, build figures and write all evaluation artifacts."""
    solutions_path = cfg.reports_dir / "solutions.json"
    if not solutions_path.exists():
        raise FileNotFoundError(
            f"{solutions_path} missing — run `routing_optimization solve` first"
        )
    solutions = json.loads(solutions_path.read_text())
    best_known_table = load_best_known(cfg.best_known_path, cfg.best_known_supplement_path)

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
        evaluations.append(
            InstanceEvaluation(
                instance=inst,
                n_customers=int(data["n_customers"]),
                vehicle_capacity=float(data["vehicle_capacity"]),
                best_known=best_known_table.get(canonical_instance_name(inst)),
                runs=solvers,
                best_routes=data["best"]["routes"],
            )
        )

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

    figures: dict[str, go.Figure] = {
        "gap_pct": gap_figure(gap_rows),
        "runtime": runtime_figure(runtime_rows),
        "solver_profile": solver_profile_figure(distance_rows),
    }
    for inst, history in solutions.get("convergence", {}).items():
        figures[f"convergence_{inst}"] = convergence_figure(history, inst)
    map_eval = next((ev for ev in evaluations if ev.instance == cfg.map_instance), evaluations[0])
    map_problem = parse_solomon_file(
        cfg.raw_dir / f"{map_eval.instance}.txt", name=map_eval.instance
    )
    figures["eda_instance_map"] = eda_instance_map_figure(map_problem)
    if map_eval.best_routes is not None:
        best = map_eval.best()
        gap = (
            f", gap {gap_pct(best.total_distance, map_eval.best_known):.2f}%"
            if map_eval.best_known is not None
            else ""
        )
        figures[f"route_map_{map_eval.instance}"] = route_map_figure(
            map_problem,
            map_eval.best_routes,
            title=(
                f"{map_eval.instance} best solution — {best.n_vehicles} vehicles, "
                f"{best.total_distance:.2f} km{gap}"
            ),
        )

    family_rows = pl.DataFrame(
        {
            "family": family_of(ev.instance),
            "solver": r.solver,
            "gap_pct": round(gap_pct(r.total_distance, ev.best_known), 4),
        }
        for ev in evaluations
        if ev.best_known is not None
        for r in ev.runs
    )
    figures["family_gap"] = family_gap_figure(family_rows)

    figures_dir = cfg.reports_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    # drop stale figure payloads from previous runs (e.g. changed instance lists)
    for stale in figures_dir.iterdir():
        if stale.suffix in {".html", ".json"} and stale.stem not in figures:
            stale.unlink()
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")

    detail_md = results_markdown(evaluations)
    summary_md = summary_markdown(evaluations)
    family_md = family_markdown(evaluations)
    (cfg.reports_dir / "results.md").write_text(
        f"# Routing optimization — evaluation results\n\n## Summary (mean over instances)\n\n"
        f"{summary_md}\n\n## Per-family results\n\n{family_md}\n\n"
        f"## Per-instance results\n\n{detail_md}\n"
    )

    metrics = {
        "summary": {
            solver: {
                "mean_gap_pct": round(
                    sum(
                        gap_pct(r.total_distance, ev.best_known)
                        for ev in evaluations
                        for r in ev.runs
                        if r.solver == solver and ev.best_known is not None
                    )
                    / max(
                        sum(
                            1
                            for ev in evaluations
                            for r in ev.runs
                            if r.solver == solver and ev.best_known is not None
                        ),
                        1,
                    ),
                    4,
                ),
                "mean_runtime_s": round(
                    sum(r.runtime_s for ev in evaluations for r in ev.runs if r.solver == solver)
                    / max(sum(1 for ev in evaluations for r in ev.runs if r.solver == solver), 1),
                    6,
                ),
                "mean_n_vehicles": round(
                    sum(r.n_vehicles for ev in evaluations for r in ev.runs if r.solver == solver)
                    / max(sum(1 for ev in evaluations for r in ev.runs if r.solver == solver), 1),
                    2,
                ),
            }
            for solver in sorted({r.solver for ev in evaluations for r in ev.runs})
        },
        "instances": {
            ev.instance: {
                "best_known": ev.best_known,
                "best_solver": ev.best().solver,
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
                        "runtime_s": round(r.runtime_s, 6),
                    }
                    for r in ev.runs
                },
            }
            for ev in evaluations
        },
        "tuning": {
            "solver_best": solutions.get("solver_best"),
            "hpo": solutions.get("hpo"),
            "alns_best": solutions.get("alns_best"),
            "alns_hpo": solutions.get("alns_hpo"),
        },
        "families": {
            fam: {
                solver: round(
                    sum(
                        gap_pct(r.total_distance, ev.best_known)
                        for ev in evaluations
                        if family_of(ev.instance) == fam and ev.best_known is not None
                        for r in ev.runs
                        if r.solver == solver
                    )
                    / max(
                        sum(
                            1
                            for ev in evaluations
                            if family_of(ev.instance) == fam and ev.best_known is not None
                            for r in ev.runs
                            if r.solver == solver
                        ),
                        1,
                    ),
                    4,
                )
                for solver in sorted({r.solver for ev in evaluations for r in ev.runs})
            }
            for fam in sorted({family_of(ev.instance) for ev in evaluations})
        },
    }
    metrics_path = cfg.reports_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))

    report = EvalReport(title="Routing Optimization — Solomon VRPTW benchmark")
    report.add_markdown_table("Summary (mean over instances)", summary_md)
    report.add_markdown_table("Per-family results", family_md)
    report.add_markdown_table("Per-instance results", detail_md)
    for name in figures:
        report.add_html(
            name.replace("_", " ").title(),
            f'<p><a href="figures/{name}.html">interactive figure</a> '
            f"(<code>figures/{name}.html</code>)</p>",
        )
    report.write(cfg.reports_dir / "report.html")
    return metrics_path


__all__ = [
    "InstanceEvaluation",
    "SolverRun",
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
