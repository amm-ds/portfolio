"""Hand-written, deterministic VRPTW heuristics.

Three solvers, no external optimization library:

- :func:`nearest_neighbor`: sequential nearest-neighbour construction with
  capacity and time-window feasibility checks at every insertion.
- :func:`clarke_wright_savings`: Clarke & Wright (1964) parallel savings with
  sequential merge application; capacity and full-route time-window checks.
- :func:`two_opt`: first-improvement 2-opt segment reversal applied to the
  better of the two construction heuristics; only moves that keep every route
  time-window feasible are accepted.

Determinism comes from sorted scans and (distance, id) tie-breaking; the run
seed is recorded in the artifacts for provenance. Distances are Euclidean with
travel time equal to distance (unit speed), as in the Solomon benchmark.
"""

import math
import random

from portfolio_core.logging import get_logger

from routing_optimization.schemas import Acceptance, Customer, Problem, RoutePlan

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


def nearest_neighbor(problem: Problem) -> RoutePlan:
    """Sequential nearest-neighbour construction.

    Greedily appends the closest customer that keeps the current route
    capacity- and time-window feasible (including the return-to-depot leg);
    opens a new route when no customer qualifies.
    """
    dist = distance_matrix(problem)
    depot = problem.depot
    unvisited = sorted(c.id for c in problem.customers[1:])
    routes: list[list[int]] = []

    while unvisited:
        # Time-oriented seed: open the route at the most urgent customer
        # (earliest due time); this keeps vehicle counts low on tight,
        # scattered instances where depot-first greedy fragments badly.
        seed = min(unvisited, key=lambda cid: (problem.customers[cid].due_time, cid))
        route: list[int] = [seed]
        c0 = problem.customers[seed]
        t = max(dist[0][seed], c0.ready_time) + c0.service_time
        if t - c0.service_time > c0.due_time + _EPS:
            raise RuntimeError(f"nearest_neighbor: customer {seed} unreachable from depot")
        load = c0.demand
        prev = seed
        unvisited.remove(seed)
        while unvisited:
            best: tuple[float, int] | None = None
            for cid in unvisited:
                c = problem.customers[cid]
                if load + c.demand > problem.vehicle_capacity + _EPS:
                    continue
                arrival = t + dist[prev][cid]
                start = max(arrival, c.ready_time)
                if start > c.due_time + _EPS:
                    continue
                candidate = (dist[prev][cid], cid)  # ties break on smaller id
                if best is None or candidate < best:
                    best = candidate
            if best is None:
                break
            cid = best[1]
            c = problem.customers[cid]
            route.append(cid)
            load += c.demand
            t = max(t + dist[prev][cid], c.ready_time) + c.service_time
            prev = cid
            unvisited.remove(cid)
        # Trim customers whose return-to-depot leg breaks the depot due time;
        # they are reconsidered on the next route.
        while route and t + dist[prev][0] > depot.due_time + _EPS:
            cid = route.pop()
            c = problem.customers[cid]
            load -= c.demand
            # recompute time at `prev` before the popped customer
            t = 0.0
            prev = 0
            for kept in route:
                ck = problem.customers[kept]
                t = max(t + dist[prev][kept], ck.ready_time) + ck.service_time
                prev = kept
            unvisited.append(cid)
            unvisited.sort()
        if not route:
            raise RuntimeError(
                f"nearest_neighbor cannot fit customer {seed} in an empty route "
                f"(due {problem.customers[seed].due_time:g} vs depot horizon {depot.due_time:g})"
            )
        routes.append(route)
        if len(routes) == problem.max_vehicles + 1:
            logger.warning(
                "nearest_neighbor exceeded the %d-vehicle fleet on %s; distance remains valid",
                problem.max_vehicles,
                problem.name,
            )

    return _finish(problem, "nearest_neighbor", routes, dist)


def randomized(problem: Problem, seed: int = 42) -> RoutePlan:
    """Seeded random-order feasible construction — baseline, no local search.

    Shuffles customers once with ``random.Random(seed)``, packs them in that
    order into capacity- and time-window-feasible routes (same per-insertion
    checks as the other constructors), then repairs: routes whose
    return-to-depot leg breaks the depot horizon are trimmed tail-first and the
    trimmed customers re-enter the pool for the next route. Fully
    deterministic for a given seed.
    """
    dist = distance_matrix(problem)
    depot = problem.depot
    rng = random.Random(seed)
    pool = [c.id for c in problem.customers[1:]]
    rng.shuffle(pool)
    routes: list[list[int]] = []

    while pool:
        route: list[int] = []
        load = 0.0
        t = 0.0
        prev = 0
        remaining: list[int] = []
        for cid in pool:
            c = problem.customers[cid]
            fits_capacity = load + c.demand <= problem.vehicle_capacity + _EPS
            if route:
                start = max(t + dist[prev][cid], c.ready_time)
            else:
                start = max(dist[0][cid], c.ready_time)
            fits_window = start <= c.due_time + _EPS
            if fits_capacity and fits_window:
                route.append(cid)
                load += c.demand
                t = start + c.service_time
                prev = cid
            else:
                remaining.append(cid)
        pool = remaining
        # Repair pass: trim customers whose return-to-depot leg breaks the
        # depot due time; they are reconsidered on the next route.
        while route and t + dist[prev][0] > depot.due_time + _EPS:
            cid = route.pop()
            c = problem.customers[cid]
            load -= c.demand
            t = 0.0
            prev = 0
            for kept in route:
                ck = problem.customers[kept]
                t = max(t + dist[prev][kept], ck.ready_time) + ck.service_time
                prev = kept
            pool.append(cid)
        if not route:
            raise RuntimeError(
                f"randomized cannot fit customer {pool[0]} in an empty route "
                f"(due {problem.customers[pool[0]].due_time:g} vs depot horizon {depot.due_time:g})"
            )
        routes.append(route)
        if len(routes) == problem.max_vehicles + 1:
            logger.warning(
                "randomized exceeded the %d-vehicle fleet on %s; distance remains valid",
                problem.max_vehicles,
                problem.name,
            )

    return _finish(problem, "randomized", routes, dist)


def clarke_wright_savings(problem: Problem) -> RoutePlan:
    """Clarke & Wright savings heuristic with time-window-aware merges.

    Starts from one route per customer (``0-i-0``), processes savings
    ``s(i,j) = d(0,i) + d(0,j) - d(i,j)`` in descending order and merges the
    two routes whenever ``i`` and ``j`` are endpoints of distinct routes, the
    combined demand fits the vehicle and the merged route is time-window
    feasible.
    """
    dist = distance_matrix(problem)
    capacity = problem.vehicle_capacity
    ids = [c.id for c in problem.customers[1:]]

    routes: dict[int, list[int]] = {i: [i] for i in ids}
    load: dict[int, float] = {i: problem.customers[i].demand for i in ids}
    first: dict[int, int] = {i: i for i in ids}
    last: dict[int, int] = {i: i for i in ids}
    route_of: dict[int, int] = {i: i for i in ids}

    savings = sorted(
        ((dist[0][i] + dist[0][j] - dist[i][j], i, j) for i in ids for j in ids if j > i),
        key=lambda s: (-s[0], s[1], s[2]),
    )

    for _s, i, j in savings:
        ri, rj = route_of[i], route_of[j]
        if ri == rj:
            continue
        a, b = routes[ri], routes[rj]
        if last[ri] == i and first[rj] == j:
            merged = a + b
        elif first[ri] == i and last[rj] == j:
            merged = b + a
        elif first[ri] == i and first[rj] == j:
            merged = a[::-1] + b
        elif last[ri] == i and last[rj] == j:
            merged = a + b[::-1]
        else:
            continue
        if load[ri] + load[rj] > capacity + _EPS:
            continue
        if not route_feasible(problem, dist, merged):
            continue
        routes[ri] = merged
        load[ri] += load[rj]
        first[ri], last[ri] = merged[0], merged[-1]
        for node in merged:
            route_of[node] = ri
        del routes[rj], load[rj], first[rj], last[rj]

    plan_routes = [routes[k] for k in sorted(routes)]
    if len(plan_routes) > problem.max_vehicles:
        raise RuntimeError(
            f"clarke_wright needs {len(plan_routes)} vehicles > fleet {problem.max_vehicles}"
        )
    return _finish(problem, "clarke_wright", plan_routes, dist)


def _intra_candidate(
    problem: Problem, dist: list[list[float]], route: list[int], i: int, j: int
) -> tuple[float, list[int]] | None:
    """2-opt segment reversal of ``route[i..j]``; (delta, candidate) or None."""
    n = len(route)
    left = route[i - 1] if i > 0 else 0
    right = route[j + 1] if j < n - 1 else 0
    delta = (
        dist[left][route[j]] + dist[route[i]][right] - dist[left][route[i]] - dist[route[j]][right]
    )
    if delta >= -_EPS:
        return None
    candidate = route[:i] + route[i : j + 1][::-1] + route[j + 1 :]
    if not route_feasible(problem, dist, candidate):
        return None
    return delta, candidate


def _inter_candidate(
    problem: Problem,
    dist: list[list[float]],
    routes: list[list[int]],
    a: int,
    b: int,
    i: int,
    j: int,
    capacity: float,
) -> tuple[float, list[int], list[int]] | None:
    """2-opt* tail exchange between routes a and b; (delta, new_a, new_b) or None."""
    ra, rb = routes[a], routes[b]
    next_a = ra[i + 1] if i + 1 < len(ra) else 0
    next_b = rb[j + 1] if j + 1 < len(rb) else 0
    delta = dist[ra[i]][next_b] + dist[rb[j]][next_a] - dist[ra[i]][next_a] - dist[rb[j]][next_b]
    if delta >= -_EPS:
        return None
    new_a = ra[: i + 1] + rb[j + 1 :]
    new_b = rb[: j + 1] + ra[i + 1 :]
    if not new_a or not new_b:  # never leave an empty route
        return None
    load_a = sum(problem.customers[cid].demand for cid in new_a)
    load_b = sum(problem.customers[cid].demand for cid in new_b)
    if load_a > capacity + _EPS or load_b > capacity + _EPS:
        return None
    if not route_feasible(problem, dist, new_a):
        return None
    if not route_feasible(problem, dist, new_b):
        return None
    return delta, new_a, new_b


def two_opt(
    problem: Problem,
    plan: RoutePlan,
    max_iterations: int = 200,
    acceptance: Acceptance = "first",
    tail_exchange: bool = True,
    trace: list[float] | None = None,
) -> RoutePlan:
    """Feasibility-checked 2-opt improvement of ``plan``.

    Move types: intra-route segment reversals, plus (unless ``tail_exchange``
    is False) inter-route 2-opt* tail exchanges. With ``acceptance="first"``
    the first improving move in scan order is applied; with ``"best"`` the
    feasible move with the most negative delta in the whole neighborhood is
    applied. Scanning is deterministic; the loop stops at a local optimum or
    after ``max_iterations`` accepted moves. When ``trace`` is given, the total
    distance is appended for the construction start and after every accepted
    move (convergence curves for figures).
    """
    dist = distance_matrix(problem)
    routes = [list(r) for r in plan.routes]
    loads = [sum(problem.customers[cid].demand for cid in r) for r in routes]
    capacity = problem.vehicle_capacity
    iterations = 0
    if trace is not None:
        trace.append(sum(route_distance(dist, r) for r in routes))

    Move = tuple[float, int, list[int], int, list[int]]

    def find_first() -> Move | None:
        """First improving move; shape (delta, x, new_x, y, new_y) with y < 0
        marking an intra-route move on route x, otherwise an inter-route move
        rewriting routes x and y."""
        for k in range(len(routes)):
            route = routes[k]
            for i in range(len(route) - 1):
                for j in range(i + 1, len(route)):
                    cand = _intra_candidate(problem, dist, route, i, j)
                    if cand is not None:
                        return cand[0], k, cand[1], -1, []
        if tail_exchange:
            for a in range(len(routes)):
                for b in range(a + 1, len(routes)):
                    for i in range(len(routes[a])):
                        for j in range(len(routes[b])):
                            icand = _inter_candidate(problem, dist, routes, a, b, i, j, capacity)
                            if icand is not None:
                                return icand[0], a, icand[1], b, icand[2]
        return None

    def find_best() -> Move | None:
        """Best (most negative delta) improving move over the full neighborhood."""
        best: Move | None = None
        for k in range(len(routes)):
            route = routes[k]
            for i in range(len(route) - 1):
                for j in range(i + 1, len(route)):
                    cand = _intra_candidate(problem, dist, route, i, j)
                    if cand is not None and (best is None or cand[0] < best[0]):
                        best = (cand[0], k, cand[1], -1, [])
        if tail_exchange:
            for a in range(len(routes)):
                for b in range(a + 1, len(routes)):
                    for i in range(len(routes[a])):
                        for j in range(len(routes[b])):
                            icand = _inter_candidate(problem, dist, routes, a, b, i, j, capacity)
                            if icand is not None and (best is None or icand[0] < best[0]):
                                best = (icand[0], a, icand[1], b, icand[2])
        return best

    find_move = find_first if acceptance == "first" else find_best
    while iterations < max_iterations:
        move = find_move()
        if move is None:
            break
        _delta, x, new_x, y, new_y = move
        if y < 0:
            routes[x] = new_x
            loads[x] = sum(problem.customers[cid].demand for cid in new_x)
        else:
            routes[x], routes[y] = new_x, new_y
            loads[x] = sum(problem.customers[cid].demand for cid in new_x)
            loads[y] = sum(problem.customers[cid].demand for cid in new_y)
        iterations += 1
        if trace is not None:
            trace.append(sum(route_distance(dist, r) for r in routes))

    if iterations >= max_iterations:
        logger.info("two_opt stopped at iteration cap %d", max_iterations)
    suffix = "+two_opt" if acceptance == "first" and tail_exchange else "+two_opt_best"
    return _finish(problem, f"{plan.solver}{suffix}", routes, dist)
