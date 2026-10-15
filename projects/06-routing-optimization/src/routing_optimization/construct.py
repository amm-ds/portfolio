"""Construction heuristics: seeded, deterministic feasible route builders.

All three produce a validated :class:`RoutePlan` via the shared
:func:`routing_optimization.routing._finish` gate, on top of the geometry and
feasibility primitives in :mod:`routing_optimization.routing`. Determinism
comes from sorted scans, (distance, id) tie-breaking and a single seeded RNG
in ``randomized``; distances are Euclidean with travel time equal to distance,
as in the Solomon benchmark.
"""

import random

from portfolio_core.logging import get_logger
from routing_optimization.routing import _EPS, _finish, distance_matrix, route_feasible
from routing_optimization.schemas import Problem, RoutePlan

logger = get_logger(__name__)


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
    if len(plan_routes) == problem.max_vehicles + 1:
        logger.warning(
            "clarke_wright exceeded the %d-vehicle fleet on %s; distance remains valid",
            problem.max_vehicles,
            problem.name,
        )
    return _finish(problem, "clarke_wright", plan_routes, dist)


