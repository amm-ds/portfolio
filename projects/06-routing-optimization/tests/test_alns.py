"""ALNS tests: feasibility, determinism, and operator-weight adaptation."""

import importlib.util
import itertools
from pathlib import Path

from routing_optimization.parser import parse_solomon
from routing_optimization.solver import (
    alns,
    clarke_wright_savings,
    distance_matrix,
    nearest_neighbor,
    route_feasible,
)

_spec = importlib.util.spec_from_file_location(
    "routing_tiny_instance", Path(__file__).parent / "tiny_instance.py"
)
assert _spec is not None and _spec.loader is not None
_tiny_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tiny_module)
TINY_INSTANCE = _tiny_module.TINY_INSTANCE


def _tiny(name: str = "T1"):
    return parse_solomon(TINY_INSTANCE, name=name)


def _start(problem):
    nn = nearest_neighbor(problem)
    cw = clarke_wright_savings(problem)
    return min((nn, cw), key=lambda p: p.total_distance)


def test_alns_feasible(tiny_problem) -> None:
    plan = alns(
        tiny_problem,
        start=_start(tiny_problem),
        seed=42,
        max_iterations=30,
        segment_length=10,
        destroy_q=2,
    )
    plan.validate_against(tiny_problem)
    dist = distance_matrix(tiny_problem)
    assert all(route_feasible(tiny_problem, dist, r) for r in plan.routes)


def test_alns_never_worsens_start(tiny_problem) -> None:
    start = _start(tiny_problem)
    plan = alns(
        tiny_problem,
        start=start,
        seed=42,
        max_iterations=30,
        segment_length=10,
        destroy_q=2,
    )
    assert plan.total_distance <= start.total_distance + 1e-9


def test_alns_is_deterministic(tiny_problem) -> None:
    kwargs = dict(seed=42, max_iterations=30, segment_length=10, destroy_q=2)
    a = alns(tiny_problem, start=_start(tiny_problem), **kwargs)
    b = alns(tiny_problem, start=_start(tiny_problem), **kwargs)
    assert a.model_dump() == b.model_dump()


def test_alns_weight_adaptation_progresses(tiny_problem) -> None:
    """Segment-end weight snapshots must exist and reward winning operators.

    Started from a poor (randomized) plan, real improvements occur, so the
    segment update must move at least one operator weight away from uniform.
    """
    from routing_optimization.solver import randomized

    stats: dict[str, list[list[float]]] = {}
    alns(
        tiny_problem,
        start=randomized(tiny_problem, seed=1),
        seed=42,
        max_iterations=40,
        segment_length=10,
        destroy_q=2,
        stats=stats,
    )
    snapshots = stats.get("destroy_weights", [])
    assert len(snapshots) >= 2  # at least two segment boundaries
    assert any(snap != [1.0, 1.0, 1.0] for snap in snapshots)  # adaptation moved


def test_alns_trace_records_best(tiny_problem) -> None:
    trace: list[float] = []
    plan = alns(
        tiny_problem,
        start=_start(tiny_problem),
        seed=42,
        max_iterations=20,
        segment_length=10,
        destroy_q=2,
        trace=trace,
    )
    assert trace[0] >= plan.total_distance - 1e-9  # starts at construction
    assert all(later <= earlier + 1e-9 for earlier, later in itertools.pairwise(trace))


def test_alns_fleet_first_objective(tiny_problem) -> None:
    """The fleet-first arm labels itself, stays feasible and never worse in
    objective: distance + penalty x vehicles must not exceed the start's."""
    start = _start(tiny_problem)
    plan = alns(
        tiny_problem,
        start=start,
        seed=42,
        max_iterations=30,
        segment_length=10,
        destroy_q=2,
        vehicle_penalty=10_000.0,
    )
    plan.validate_against(tiny_problem)
    dist = distance_matrix(tiny_problem)
    assert all(route_feasible(tiny_problem, dist, r) for r in plan.routes)
    assert plan.solver == "alns_fleet"
    # the penalty-dominated objective of the result never exceeds the start's
    start_obj = start.total_distance + 10_000.0 * start.n_vehicles
    plan_obj = plan.total_distance + 10_000.0 * plan.n_vehicles
    assert plan_obj <= start_obj + 1e-9


def test_alns_fleet_is_deterministic(tiny_problem) -> None:
    kwargs = dict(
        seed=42, max_iterations=30, segment_length=10, destroy_q=2, vehicle_penalty=10_000.0
    )
    a = alns(tiny_problem, start=_start(tiny_problem), **kwargs)
    b = alns(tiny_problem, start=_start(tiny_problem), **kwargs)
    assert a.model_dump() == b.model_dump()


def test_alns_zero_penalty_matches_plain_name(tiny_problem) -> None:
    plan = alns(
        tiny_problem,
        start=_start(tiny_problem),
        seed=42,
        max_iterations=20,
        segment_length=10,
        destroy_q=2,
        vehicle_penalty=0.0,
    )
    assert plan.solver == "alns"
