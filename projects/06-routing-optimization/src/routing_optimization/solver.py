"""Improvement metaheuristics: 2-opt and adaptive large-neighborhood search.

- :func:`two_opt` — feasibility-checked 2-opt (intra-route reversals +
  inter-route 2-opt* tail exchanges) with first- or best-improvement
  acceptance.
- :func:`alns` — Ropke-Pisinger adaptive large-neighborhood search: destroy
  (random / worst / Shaw time-window relatedness), regret-2 repair, segment
  operator-weight adaptation, simulated-annealing acceptance.

Both build on the shared primitives in :mod:`routing_optimization.routing`
and validate output through the same ``_finish`` gate. The construction
heuristics live in :mod:`routing_optimization.construct`; they (and the
routing primitives) are re-exported here for backward compatibility.
"""

import math
import random
from typing import Literal

from portfolio_core.logging import get_logger
from routing_optimization.construct import (
    clarke_wright_savings,
    nearest_neighbor,
    randomized,
)
from routing_optimization.routing import (
    _EPS,
    _finish,
    distance_matrix,
    euclidean,
    route_distance,
    route_feasible,
)
from routing_optimization.schemas import Acceptance, Problem, RoutePlan

logger = get_logger(__name__)


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
