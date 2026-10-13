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
from typing import Literal

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
    if len(plan_routes) == problem.max_vehicles + 1:
        logger.warning(
            "clarke_wright exceeded the %d-vehicle fleet on %s; distance remains valid",
            problem.max_vehicles,
            problem.name,
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


# ---------------------------------------------------------------------------
# Adaptive large-neighborhood search (ALNS)
#


def _removal_gain(dist: list[list[float]], route: list[int], pos: int) -> float:
    """Distance saved by removing ``route[pos]`` (depot-aware)."""
    c = route[pos]
    prev = route[pos - 1] if pos > 0 else 0
    nxt = route[pos + 1] if pos + 1 < len(route) else 0
    return dist[prev][c] + dist[c][nxt] - dist[prev][nxt]


def _destroy_random(
    dist: list[list[float]],
    routes: list[list[int]],
    q: int,
    rng: random.Random,
) -> tuple[list[int], list[list[int]]]:
    """Random removal of q customers."""
    del dist  # distance-free operator
    flat = [c for r in routes for c in r]
    removed = rng.sample(flat, min(q, len(flat)))
    drop = set(removed)
    reduced = [[c for c in r if c not in drop] for r in routes]
    return removed, [r for r in reduced if r]


def _destroy_worst(
    dist: list[list[float]],
    routes: list[list[int]],
    q: int,
    rng: random.Random,
) -> tuple[list[int], list[list[int]]]:
    """Worst removal: q times the highest-removal-gain customer among a random
    candidate subset (randomized tie-break, Ropke-Pisinger style)."""
    present = [c for r in routes for c in r]
    removed: list[int] = []
    for _ in range(min(q, len(present))):
        candidates = rng.sample(present, min(5, len(present)))
        worst = max(candidates, key=lambda cid: _removal_gain_for(dist, routes, cid))
        removed.append(worst)
        present.remove(worst)
    drop = set(removed)
    reduced = [[c for c in r if c not in drop] for r in routes]
    return removed, [r for r in reduced if r]


def _removal_gain_for(dist: list[list[float]], routes: list[list[int]], cid: int) -> float:
    for r in routes:
        if cid in r:
            return _removal_gain(dist, r, r.index(cid))
    return 0.0


def _shaw_relatedness(problem: Problem, dist: list[list[float]], a: int, b: int) -> float:
    """Time-window-and-distance relatedness between two customers (higher = more related)."""
    ca, cb = problem.customers[a], problem.customers[b]
    tw_gap = abs(ca.ready_time - cb.ready_time) + abs(ca.due_time - cb.due_time)
    return 1.0 / (1.0 + dist[a][b] + 0.5 * tw_gap)


def _destroy_shaw(
    problem: Problem,
    dist: list[list[float]],
    routes: list[list[int]],
    q: int,
    rng: random.Random,
) -> tuple[list[int], list[list[int]]]:
    """Shaw removal: seed a random customer, then repeatedly remove the most
    time-window-related customer to the removal set (randomized among top-3)."""
    present = [c for r in routes for c in r]
    seed = rng.choice(present)
    removed = [seed]
    present.remove(seed)
    while present and len(removed) < q:
        related = sorted(
            present,
            key=lambda cid: (-_shaw_relatedness(problem, dist, removed[-1], cid), cid),
        )
        pick = related[rng.randrange(min(3, len(related)))]
        removed.append(pick)
        present.remove(pick)
    drop = set(removed)
    reduced = [[c for c in r if c not in drop] for r in routes]
    return removed, [r for r in reduced if r]


def _insertion_options(
    problem: Problem,
    dist: list[list[float]],
    routes: list[list[int]],
    loads: list[float],
    cid: int,
) -> list[tuple[float, int, int, list[int]]]:
    """All feasible (delta, route_idx, pos, new_route) insertion slots for cid."""
    c = problem.customers[cid]
    options: list[tuple[float, int, int, list[int]]] = []
    for k, route in enumerate(routes):
        if loads[k] + c.demand > problem.vehicle_capacity + _EPS:
            continue
        for pos in range(len(route) + 1):
            prev = route[pos - 1] if pos > 0 else 0
            nxt = route[pos] if pos < len(route) else 0
            candidate = [*route[:pos], cid, *route[pos:]]
            if not route_feasible(problem, dist, candidate):
                continue
            delta = dist[prev][cid] + dist[cid][nxt] - dist[prev][nxt]
            options.append((delta, k, pos, candidate))
    return options


def _regret2_repair(
    problem: Problem,
    dist: list[list[float]],
    routes: list[list[int]],
    removed: list[int],
) -> list[list[int]] | None:
    """Greedy regret-2 insertion; None when a customer has no feasible slot."""
    capacity = problem.vehicle_capacity
    routes = [list(r) for r in routes if r]
    loads = [sum(problem.customers[cid].demand for cid in r) for r in routes]
    pending = list(removed)
    big = 1e9
    while pending:
        choice: tuple[tuple[float, float, int], int, int, int] | None = None
        for cid in sorted(pending):
            options = _insertion_options(problem, dist, routes, loads, cid)
            if not options:
                return None  # dead end: abort the repair, keep the incumbent
            options.sort(key=lambda o: (o[0], o[1], o[2]))
            best = options[0]
            regret = options[1][0] - best[0] if len(options) > 1 else big + best[0]
            key = (regret, -best[0], -cid)  # deterministic tie-breaks
            if choice is None or key > choice[0]:
                choice = (key, cid, best[1], best[2])
        assert choice is not None  # pending is non-empty, so the loop set it
        _key, cid, k, pos = choice
        routes[k] = [*routes[k][:pos], cid, *routes[k][pos:]]
        loads[k] += problem.customers[cid].demand
        if loads[k] > capacity + _EPS:  # defensive; capacity was checked per option
            return None
        pending.remove(cid)
    return routes


def _total_distance(dist: list[list[float]], routes: list[list[int]]) -> float:
    return sum(route_distance(dist, r) for r in routes)


def _weighted_index(weights: list[float], rng: random.Random) -> int:
    total = sum(weights)
    pick = rng.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if pick <= acc:
            return i
    return len(weights) - 1


def alns(
    problem: Problem,
    start: RoutePlan,
    seed: int = 42,
    max_iterations: int = 120,
    segment_length: int = 50,
    reaction_factor: float = 0.3,
    init_weights: Literal["uniform", "biased"] = "uniform",
    destroy_q: int = 10,
    trace: list[float] | None = None,
    stats: dict[str, list[list[float]]] | None = None,
) -> RoutePlan:
    """Adaptive large-neighborhood search (Ropke & Pisinger, 2006).

    Each iteration destroys ``destroy_q`` customers with a roulette-selected
    destroy operator (random / worst / Shaw time-window relatedness) and
    repairs with regret-2 insertion, accepting slightly worse solutions via
    geometrically-cooled simulated annealing. Operator weights adapt per
    segment from scores (new best 3 / improvement 2 / accepted 1). Fully
    seeded: one ``random.Random(seed)`` drives every decision.
    """
    dist = distance_matrix(problem)
    rng = random.Random(seed)
    destroy_ops = [
        lambda rs, q: _destroy_random(dist, rs, q, rng),
        lambda rs, q: _destroy_worst(dist, rs, q, rng),
        lambda rs, q: _destroy_shaw(problem, dist, rs, q, rng),
    ]

    weights_d = [0.6, 1.2, 1.0] if init_weights == "biased" else [1.0, 1.0, 1.0]
    weights_r = [1.0]
    scores_d = [0.0, 0.0, 0.0]
    counts_d = [0, 0, 0]
    scores_r = [0.0]
    counts_r = [0]

    current = [list(r) for r in start.routes]
    current_dist = _total_distance(dist, current)
    best = [list(r) for r in current]
    best_dist = current_dist
    if trace is not None:
        trace.append(best_dist)

    temp0 = 0.05 * start.total_distance
    temp_end = 1e-3
    for it in range(max_iterations):
        if it > 0 and it % segment_length == 0:
            for i in range(3):
                if counts_d[i] > 0:
                    weights_d[i] = (1 - reaction_factor) * weights_d[i] + (
                        reaction_factor * scores_d[i] / counts_d[i]
                    )
                scores_d[i] = 0.0
                counts_d[i] = 0
            for i in range(len(weights_r)):
                if counts_r[i] > 0:
                    weights_r[i] = (1 - reaction_factor) * weights_r[i] + (
                        reaction_factor * scores_r[i] / counts_r[i]
                    )
                scores_r[i] = 0.0
                counts_r[i] = 0
            if stats is not None:
                stats.setdefault("destroy_weights", []).append(list(weights_d))
                stats.setdefault("repair_weights", []).append(list(weights_r))

        di = _weighted_index(weights_d, rng)
        removed, reduced = destroy_ops[di](current, destroy_q)
        repaired = _regret2_repair(problem, dist, reduced, removed)
        counts_d[di] += 1
        if repaired is None:
            continue
        counts_r[0] += 1
        new_dist = _total_distance(dist, repaired)

        score = 0.0
        if new_dist < best_dist - _EPS:
            score = 3.0
        elif new_dist < current_dist - _EPS:
            score = 2.0
        temp = temp0 * (temp_end / temp0) ** (it / max(max_iterations - 1, 1))
        accepted = new_dist <= current_dist + _EPS or rng.random() < math.exp(
            -(new_dist - current_dist) / max(temp, 1e-9)
        )
        if accepted:
            score = max(score, 1.0)
            current, current_dist = repaired, new_dist
            if new_dist < best_dist - _EPS:
                best = [list(r) for r in repaired]
                best_dist = new_dist
        scores_d[di] += score
        scores_r[0] += score
        if trace is not None:
            trace.append(best_dist)

    return _finish(problem, "alns", best, dist)
