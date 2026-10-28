"""Property tests over the committed solution artifact (``reports/solutions.json``).

Scope (hand-checked on C101 before writing): the committed best plans — one
per Solomon instance — are feasible under the project's own semantics
(:func:`route_feasible`: capacity per route, every customer visited inside its
time window with waiting allowed, depot due time bounding the return leg), and
the committed ``total_distance`` reproduces exactly from the committed routes.
Both properties are asserted here for all 56 instances, plus a hypothesis
property: any order-preserving subsequence of a feasible route is still
feasible (dropping customers cannot add load or delay a remaining visit).
"""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from routing_optimization.parser import parse_solomon_file
from routing_optimization.routing import distance_matrix, route_distance, route_feasible

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOLUTIONS = PROJECT_ROOT / "reports" / "solutions.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

_COMMITTED = json.loads(SOLUTIONS.read_text(encoding="utf-8"))["instances"]
_INSTANCES = sorted(_COMMITTED)


def _committed_routes(name: str) -> list[list[int]]:
    return [list(r) for r in _COMMITTED[name]["best"]["routes"]]


@pytest.mark.parametrize("name", _INSTANCES)
def test_committed_solution_is_feasible(name: str) -> None:
    """Every committed best plan: once-only service, capacity, time windows."""
    problem = parse_solomon_file(RAW_DIR / f"{name}.txt")
    dist = distance_matrix(problem)
    routes = _committed_routes(name)

    served = [cid for route in routes for cid in route]
    assert sorted(served) == list(range(1, problem.n_customers + 1))
    for route in routes:
        assert route_feasible(problem, dist, route)


@pytest.mark.parametrize("name", _INSTANCES)
def test_committed_total_distance_matches_routes(name: str) -> None:
    """The committed total is not a stale number: it recomputes from the routes."""
    problem = parse_solomon_file(RAW_DIR / f"{name}.txt")
    dist = distance_matrix(problem)
    total = sum(route_distance(dist, r) for r in _committed_routes(name))
    assert total == pytest.approx(_COMMITTED[name]["best"]["total_distance"], abs=1e-3)


@given(
    name=st.sampled_from(_INSTANCES),
    cut=st.lists(st.integers(min_value=0, max_value=19), min_size=1, max_size=8, unique=True),
)
@settings(deadline=None)
def test_subsequence_of_feasible_route_stays_feasible(name: str, cut: list[int]) -> None:
    """Order-preserving subsequences of a feasible route remain feasible.

    Dropping customers removes demand and can only shorten travel, so neither
    capacity nor any remaining time window can break; the simulator check is
    the contract, this pins the intuition against regressions.
    """
    problem = parse_solomon_file(RAW_DIR / f"{name}.txt")
    dist = distance_matrix(problem)
    pool = [r for r in _committed_routes(name) if len(r) > 1]
    route = max(pool, key=len)
    keep = sorted({i % len(route) for i in cut})
    sub = [route[i] for i in keep]
    assert route_feasible(problem, dist, sub)
