"""Hinted cross-check solver: time-bounded OR-Tools CP-SAT model for the VRPTW.

An incumbent-improvement probe for our hand-written ladder — NOT an
independent baseline, because the construction-heuristic plan is injected as a
solution hint and returned unchanged when the time limit expires. A classic
CP-SAT routing model: one circuit per (bounded) vehicle over the
depot + customers, time and capacity propagated along arcs, objective = total
distance.

The model is kept small enough for a ~10 s single-worker solve on the
100-customer Solomon instances by (a) capping the fleet at the hinted fleet
plus a small slack and (b) building travel arcs only where a necessary
time-window condition holds (``ready_i + service_i + dist_ij <= due_j``) —
the vast majority of the 100-by-100 arc graph can never appear in a feasible
solution. Window bounds are posted once per (vehicle, node) via the node's
single incoming arc, not per arc.

Determinism-within-limit: single search worker, fixed seed, fixed hint. The
time bound makes bit-exact reproducibility impossible to promise across
machines, so callers should treat the result as best-effort within the limit
(tests assert feasibility and near-determinism, not exact equality). When the
limit expires before CP-SAT confirms any solution (status UNKNOWN), the
hinted plan is returned unchanged — the arm never makes things worse.
"""

import time
from itertools import pairwise

from ortools.sat.python import cp_model
from portfolio_core.logging import get_logger

from routing_optimization.routing import _finish, distance_matrix
from routing_optimization.schemas import Problem, RoutePlan

logger = get_logger(__name__)

_FEASIBLE_STATUSES = (cp_model.OPTIMAL, cp_model.FEASIBLE)


def _extract_routes(
    solver: cp_model.CpSolver, arcs: dict[tuple[int, int, int], cp_model.IntVar], n: int, fleet: int
) -> list[list[int]] | None:
    """Routes from the solver assignment: one chain per used vehicle."""
    used: dict[int, list[tuple[int, int]]] = {}
    for (v, i, j), var in arcs.items():
        if i != j and solver.value(var):
            used.setdefault(v, []).append((i, j))
    routes: list[list[int]] = []
    for v in range(fleet):
        nxt = dict(used.get(v, []))
        if 0 not in nxt:
            continue
        route: list[int] = []
        node = nxt[0]
        seen = {0}
        while node != 0:
            if node in seen or node < 1 or node > n:
                return None  # malformed chain: reject the incumbent
            seen.add(node)
            route.append(node)
            node = nxt.get(node, 0)
        routes.append(route)
    return routes or None


def ortools_cp(
    problem: Problem,
    hint: RoutePlan,
    time_limit_s: float = 10.0,
    max_vehicles: int = 20,
    fleet_slack: int = 3,
    seed: int = 42,
) -> RoutePlan:
    """Time-bounded CP-SAT solution of the VRPTW, hinted by ``hint``.

    The model fleet is ``min(instance fleet, max_vehicles, hint fleet +
    fleet_slack)`` so the hint is always inside the model — a feasible
    incumbent exists from the start and the limit only ever improves on it.
    Travel arcs are built only between customers whose time windows make them
    consecutive-compatible (necessary condition), which keeps the model small
    enough for the wall-time limit. Feasibility of the returned plan is
    re-verified by ``_finish``; if the limit expires before CP-SAT confirms a
    solution, the hint is returned unchanged.
    """
    dist = distance_matrix(problem)
    customers = problem.customers
    n = problem.n_customers
    depot = problem.depot
    fleet = min(problem.max_vehicles, max_vehicles, hint.n_vehicles + fleet_slack)
    horizon = depot.due_time
    capacity = problem.vehicle_capacity
    big_m = int(horizon + max(max(row) for row in dist))
    ready = [c.ready_time for c in customers]
    due = [c.due_time for c in customers]
    serv = [c.service_time for c in customers]
    demand = [c.demand for c in customers]

    # Necessary time-window condition for i -> j to appear in a feasible route.
    allowed: list[list[int]] = [
        [j for j in range(n + 1) if j != i and ready[i] + serv[i] + dist[i][j] <= due[j] + 1e-9]
        for i in range(n + 1)
    ]

    model = cp_model.CpModel()
    arcs: dict[tuple[int, int, int], cp_model.IntVar] = {}
    for v in range(fleet):
        arc_literals = []
        for i in range(n + 1):
            for j in allowed[i]:
                lit = model.new_bool_var(f"x_{v}_{i}_{j}")
                arcs[(v, i, j)] = lit
                arc_literals.append((i, j, lit))
        for i in range(n + 1):  # self-loops: node not on v's circuit
            lit = model.new_bool_var(f"x_{v}_{i}_{i}")
            arcs[(v, i, i)] = lit
            arc_literals.append((i, i, lit))
        model.add_circuit(arc_literals)

    # predecessors of each node, for exactly-once and window constraints
    preds: list[list[int]] = [[i for i in range(n + 1) if j in allowed[i]] for j in range(n + 1)]

    times: dict[tuple[int, int], cp_model.IntVar] = {}
    loads: dict[tuple[int, int], cp_model.IntVar] = {}
    returns = [model.new_int_var(0, int(horizon), f"end_{v}") for v in range(fleet)]
    for v in range(fleet):
        for j in range(n + 1):
            times[(v, j)] = model.new_int_var(0, int(horizon), f"t_{v}_{j}")
            loads[(v, j)] = model.new_int_var(0, int(capacity), f"l_{v}_{j}")
        served: list[cp_model.IntVar] = []
        for i in range(n + 1):
            for j in allowed[i]:
                lit = arcs[(v, i, j)]
                travel = round(dist[i][j])
                if j == 0:
                    # return leg: separate timestamp — depot departure
                    # (times[(v, 0)]) and arrival back (returns[v]) must not
                    # share a variable, or every route is a t >= t cycle.
                    model.add(
                        returns[v] >= times[(v, i)] + int(serv[i]) + travel - big_m * (1 - lit)
                    )
                else:
                    model.add(
                        times[(v, j)] >= times[(v, i)] + int(serv[i]) + travel - big_m * (1 - lit)
                    )
                    model.add(
                        loads[(v, j)] >= loads[(v, i)] + int(demand[j]) - int(capacity) * (1 - lit)
                    )
                    served.append(lit)
        # a vehicle serving any customer must leave the depot (its depot
        # self-loop off), keeping customers off depot-less fake circuits
        model.add(sum(served) <= n * (1 - arcs[(v, 0, 0)]))
        for j in range(1, n + 1):
            in_sum = sum(arcs[(v, i, j)] for i in preds[j] if i != j)
            # visit windows: enforced exactly when j is on v's circuit
            model.add(times[(v, j)] >= int(ready[j]) - big_m * (1 - in_sum))
            model.add(times[(v, j)] <= int(due[j]) + big_m * (1 - in_sum))

    for j in range(1, n + 1):  # every customer served exactly once
        model.add(sum(arcs[(v, i, j)] for v in range(fleet) for i in preds[j] if i != j) == 1)

    model.minimize(sum(round(dist[i][j]) * lit for (v, i, j), lit in arcs.items() if i != j))

    # Hint: the construction plan. Used vehicles get their chains (self-loops
    # at unvisited nodes); unused vehicles self-loop everywhere. Zero-hints
    # for the remaining travel arcs are omitted — partial hints are enough.
    assigned: set[tuple[int, int, int]] = set()
    for v in range(fleet):
        if v < hint.n_vehicles:
            chain = [0, *hint.routes[v], 0]
            for i in range(n + 1):
                if i not in chain:
                    assigned.add((v, i, i))
            for a, b in pairwise(chain):
                assigned.add((v, a, b))
        else:
            for i in range(n + 1):
                assigned.add((v, i, i))
    for key in assigned:
        model.add_hint(arcs[key], 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    t0 = time.perf_counter()
    status = solver.solve(model)
    runtime = time.perf_counter() - t0
    logger.info(
        "ortools_cp %s: status=%s objective=%s bound=%s (%.1fs)",
        problem.name,
        solver.status_name(status),
        solver.objective_value,
        solver.best_objective_bound,
        runtime,
    )

    routes: list[list[int]] | None = None
    if status in _FEASIBLE_STATUSES:
        routes = _extract_routes(solver, arcs, n, fleet)
        if routes is not None and len({c for r in routes for c in r}) != n:
            # customers parked on a depot-less circuit vanish from the depot
            # chains — degenerate solution, treat as no usable incumbent
            logger.warning("ortools_cp %s: incomplete coverage, falling back to hint", problem.name)
            routes = None
    if routes is None:  # limit hit before any usable solution: fall back to the hint
        logger.warning("ortools_cp %s: no usable incumbent, falling back to hint", problem.name)
        routes = [list(r) for r in hint.routes]
    return _finish(problem, "ortools_cp", routes, dist)
