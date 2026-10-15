"""Shared geometry and feasibility core for all VRPTW solvers.

Every solver module (``construct``, ``solver``) builds on these primitives:
Euclidean distances, route simulation against capacity and time windows, and
the :func:`_finish` gate that turns raw routes into a validated
:class:`RoutePlan`.
"""

import math

from portfolio_core.logging import get_logger
from routing_optimization.schemas import Customer, Problem, RoutePlan

logger = get_logger(__name__)

_EPS = 1e-9


def euclidean(a: Customer, b: Customer) -> float:
    """Euclidean distance between two customers."""
    return math.hypot(a.x - b.x, a.y - b.y)


def distance_matrix(problem: Problem) -> list[list[float]]:
    """Full symmetric Euclidean distance matrix indexed by customer id."""
    n = len(problem.customers)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        ci = problem.customers[i]
        for j in range(i + 1, n):
            d = euclidean(ci, problem.customers[j])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def route_distance(dist: list[list[float]], route: list[int]) -> float:
    """Route length including the depot legs ``0 -> ... -> 0``."""
    total = 0.0
    prev = 0
    for cid in route:
        total += dist[prev][cid]
        prev = cid
    return total + dist[prev][0]


def route_feasible(problem: Problem, dist: list[list[float]], route: list[int]) -> bool:
    """Simulate a route; True iff capacity and all time windows are respected.

    Vehicles may arrive before ``ready_time`` and wait. The depot's own due
    time bounds the return leg.
    """
    depot = problem.depot
    t = 0.0
    load = 0.0
    prev = 0
    for cid in route:
        c = problem.customers[cid]
        load += c.demand
        if load > problem.vehicle_capacity + _EPS:
            return False
        arrival = t + dist[prev][cid]
        start = max(arrival, c.ready_time)
        if start > c.due_time + _EPS:
            return False
        t = start + c.service_time
        prev = cid
    return t + dist[prev][0] <= depot.due_time + _EPS


def _finish(
    problem: Problem, solver: str, routes: list[list[int]], dist: list[list[float]]
) -> RoutePlan:
    """Build a validated :class:`RoutePlan`, refusing infeasible routes."""
    for k, route in enumerate(routes):
        if not route:
            raise ValueError(f"{solver}: empty route {k}")
        if not route_feasible(problem, dist, route):
            raise ValueError(f"{solver}: route {k} violates capacity or time windows")
    total = sum(route_distance(dist, r) for r in routes)
    plan = RoutePlan(
        instance=problem.name,
        solver=solver,
        routes=routes,
        total_distance=total,
        n_vehicles=len(routes),
    )
    plan.validate_against(problem)
    return plan
