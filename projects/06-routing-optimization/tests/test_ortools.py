"""OR-Tools CP-SAT reference-solver tests: feasibility, determinism-within-limit.

The time bound makes bit-exact reproducibility impossible to promise across
machines, so determinism is asserted as "same machine, same limit": both runs
must be feasible, never worse than the hint, and land within a small tolerance
(single worker, fixed seed, fixed hint make them effectively identical).
"""

import pytest
from routing_optimization.ortools_solver import ortools_cp, ortools_cp_unhinted
from routing_optimization.routing import distance_matrix, route_feasible
from routing_optimization.solver import clarke_wright_savings, nearest_neighbor

LIMIT_S = 2.0


def _hint(problem):
    nn = nearest_neighbor(problem)
    cw = clarke_wright_savings(problem)
    return min((nn, cw), key=lambda p: p.total_distance)


def test_ortools_cp_feasible_and_validated(tiny_problem) -> None:
    hint = _hint(tiny_problem)
    plan = ortools_cp(tiny_problem, hint=hint, time_limit_s=LIMIT_S, seed=42)
    plan.validate_against(tiny_problem)  # exactly-once + capacity hard gate
    dist = distance_matrix(tiny_problem)
    assert all(route_feasible(tiny_problem, dist, r) for r in plan.routes)
    assert plan.solver == "ortools_cp"


def test_ortools_cp_never_worse_than_hint(tiny_problem) -> None:
    hint = _hint(tiny_problem)
    plan = ortools_cp(tiny_problem, hint=hint, time_limit_s=LIMIT_S, seed=42)
    assert plan.total_distance <= hint.total_distance + 1e-9
    assert plan.n_vehicles <= hint.n_vehicles + 1e-9


def test_ortools_cp_deterministic_within_limit(tiny_problem) -> None:
    hint = _hint(tiny_problem)
    a = ortools_cp(tiny_problem, hint=hint, time_limit_s=LIMIT_S, seed=42)
    b = ortools_cp(tiny_problem, hint=hint, time_limit_s=LIMIT_S, seed=42)
    assert a.n_vehicles == b.n_vehicles
    assert a.total_distance == pytest.approx(b.total_distance, abs=1e-6)
    assert a.routes == b.routes


def test_ortools_cp_unhinted_solves_tiny(tiny_problem) -> None:
    """Unhinted at the tiny scale: a feasible, validated, certified plan."""
    plan, status, runtime = ortools_cp_unhinted(tiny_problem, time_limit_s=LIMIT_S, seed=42)
    assert status in ("OPTIMAL", "FEASIBLE")
    assert plan is not None
    plan.validate_against(tiny_problem)
    dist = distance_matrix(tiny_problem)
    assert all(route_feasible(tiny_problem, dist, r) for r in plan.routes)
    assert plan.solver == "ortools_cp_unhinted"
    assert runtime > 0


def test_ortools_cp_unhinted_deterministic(tiny_problem) -> None:
    a = ortools_cp_unhinted(tiny_problem, time_limit_s=LIMIT_S, seed=42)
    b = ortools_cp_unhinted(tiny_problem, time_limit_s=LIMIT_S, seed=42)
    assert a[1] == b[1]  # status
    assert (a[0] is None) == (b[0] is None)
    if a[0] is not None and b[0] is not None:
        assert a[0].n_vehicles == b[0].n_vehicles
        assert a[0].total_distance == pytest.approx(b[0].total_distance, abs=1e-6)
        assert a[0].routes == b[0].routes


def test_ortools_cp_unhinted_no_hint_fallback(tiny_problem) -> None:
    """The unhinted arm never silently substitutes another solver's plan.

    Whatever it returns is labeled as its own; when it solves the tiny
    instance, its plan stands on its own against the hinted model's.
    """
    plan, status, _ = ortools_cp_unhinted(tiny_problem, time_limit_s=LIMIT_S, seed=42)
    assert plan is None or plan.solver == "ortools_cp_unhinted"
    assert status
