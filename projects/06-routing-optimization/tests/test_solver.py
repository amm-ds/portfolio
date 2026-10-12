"""Solver tests: feasibility (capacity + time windows) on the tiny instance."""

import pytest
from routing_optimization.schemas import Problem, RoutePlan
from routing_optimization.solver import (
    clarke_wright_savings,
    distance_matrix,
    nearest_neighbor,
    randomized,
    route_feasible,
    two_opt,
)


def _assert_feasible(problem: Problem, plan: RoutePlan) -> None:
    plan.validate_against(problem)  # exactly-once + capacity
    dist = distance_matrix(problem)
    assert all(route_feasible(problem, dist, r) for r in plan.routes), (
        f"{plan.solver} produced a time-window-infeasible route"
    )


def test_nearest_neighbor_feasible(tiny_problem: Problem) -> None:
    plan = nearest_neighbor(tiny_problem)
    _assert_feasible(tiny_problem, plan)
    assert plan.n_vehicles <= tiny_problem.max_vehicles


def test_clarke_wright_feasible(tiny_problem: Problem) -> None:
    plan = clarke_wright_savings(tiny_problem)
    _assert_feasible(tiny_problem, plan)
    assert plan.n_vehicles <= tiny_problem.max_vehicles


def test_randomized_feasible(tiny_problem: Problem) -> None:
    plan = randomized(tiny_problem, seed=42)
    _assert_feasible(tiny_problem, plan)


def test_randomized_is_deterministic_per_seed(tiny_problem: Problem) -> None:
    a = randomized(tiny_problem, seed=42)
    b = randomized(tiny_problem, seed=42)
    assert a.model_dump() == b.model_dump()


def test_randomized_respects_seed(tiny_problem: Problem) -> None:
    """Different seeds must shuffle differently (trivially true on 5 customers)."""
    assert randomized(tiny_problem, seed=1).routes != randomized(tiny_problem, seed=2).routes


def test_randomized_is_feasible_but_worse_than_savings(tiny_problem: Problem) -> None:
    """On the tiny instance the randomized baseline must stay a baseline."""
    rnd = randomized(tiny_problem, seed=42)
    cw = clarke_wright_savings(tiny_problem)
    assert rnd.total_distance >= cw.total_distance - 1e-9


def test_two_opt_improves_and_stays_feasible(tiny_problem: Problem) -> None:
    base = clarke_wright_savings(tiny_problem)
    improved = two_opt(tiny_problem, base, max_iterations=200)
    _assert_feasible(tiny_problem, improved)
    assert improved.total_distance <= base.total_distance + 1e-9


def test_two_opt_never_worsens_neither_base(tiny_problem: Problem) -> None:
    """2-opt on the better of the two construction heuristics helps or ties."""
    nn = nearest_neighbor(tiny_problem)
    cw = clarke_wright_savings(tiny_problem)
    base = nn if nn.total_distance <= cw.total_distance else cw
    improved = two_opt(tiny_problem, base, max_iterations=200)
    assert improved.total_distance <= min(nn.total_distance, cw.total_distance) + 1e-9


def test_solvers_are_deterministic(tiny_problem: Problem) -> None:
    first = nearest_neighbor(tiny_problem)
    second = nearest_neighbor(tiny_problem)
    assert first.model_dump() == second.model_dump()
    a = clarke_wright_savings(tiny_problem)
    b = clarke_wright_savings(tiny_problem)
    assert a.routes == b.routes


def test_route_distance_depot_legs(tiny_problem: Problem) -> None:
    """Known geometry: depot(50,50) -> 1(52,50) -> 2(50,52) -> depot = 2 + 2.828 + 2."""
    from routing_optimization.solver import route_distance

    dist = distance_matrix(tiny_problem)
    d = route_distance(dist, [1, 2])
    assert d == pytest.approx(2.0 + 8.0**0.5 + 2.0, rel=1e-9)


def test_route_feasible_respects_due_time(tiny_problem: Problem) -> None:
    """Customer 2 opens at t=50; a route that reaches it too late is infeasible."""
    dist = distance_matrix(tiny_problem)
    assert route_feasible(tiny_problem, dist, [1, 2, 3])
    late = tiny_problem.model_copy(
        update={
            "customers": [
                c.model_copy(update={"due_time": 5.0}) if c.id == 2 else c
                for c in tiny_problem.customers
            ]
        }
    )
    assert not route_feasible(late, dist, [1, 2, 3])
