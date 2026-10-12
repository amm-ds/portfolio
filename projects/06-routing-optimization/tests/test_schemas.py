"""Validator tests: exactly-once service and capacity enforcement."""

import importlib.util
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from routing_optimization.parser import parse_solomon
from routing_optimization.schemas import Problem, RoutePlan

_spec = importlib.util.spec_from_file_location(
    "routing_tiny_instance", Path(__file__).parent / "tiny_instance.py"
)
assert _spec is not None and _spec.loader is not None
_tiny_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tiny_module)
TINY_INSTANCE = _tiny_module.TINY_INSTANCE


def _plan(routes: list[list[int]], distance: float = 100.0) -> RoutePlan:
    return RoutePlan(
        instance="TINY",
        solver="test",
        routes=routes,
        total_distance=distance,
        n_vehicles=len(routes),
    )


def test_valid_plan_passes(tiny_problem: Problem) -> None:
    plan = _plan([[1, 2, 3], [4, 5]])
    plan.validate_against(tiny_problem)  # no raise


def test_duplicate_customer_rejected(tiny_problem: Problem) -> None:
    plan = _plan([[1, 2, 3, 3], [4, 5]])
    with pytest.raises(ValueError, match="more than once"):
        plan.validate_against(tiny_problem)


def test_unvisited_customer_rejected(tiny_problem: Problem) -> None:
    plan = _plan([[1, 2, 3]])
    with pytest.raises(ValueError, match="never served"):
        plan.validate_against(tiny_problem)


def test_unknown_customer_rejected(tiny_problem: Problem) -> None:
    plan = _plan([[1, 2, 3, 99], [4, 5]])
    with pytest.raises(ValueError, match="unknown customer"):
        plan.validate_against(tiny_problem)


def test_depot_inside_route_rejected(tiny_problem: Problem) -> None:
    plan = _plan([[0, 1, 2, 3], [4, 5]])
    with pytest.raises(ValueError, match="depot"):
        plan.validate_against(tiny_problem)


def test_capacity_violation_rejected(tiny_problem: Problem) -> None:
    problem = Problem(name="TIGHT", customers=tiny_problem.customers, vehicle_capacity=40.0)
    plan = _plan([[1, 2, 3, 4, 5]])
    with pytest.raises(ValueError, match="exceeds capacity"):
        plan.validate_against(problem)


def test_empty_route_rejected(tiny_problem: Problem) -> None:
    plan = RoutePlan(
        instance="TINY",
        solver="test",
        routes=[[1, 2, 3], []],
        total_distance=100.0,
        n_vehicles=2,
    )
    with pytest.raises(ValueError, match="empty route"):
        plan.validate_against(tiny_problem)


def test_vehicle_count_mismatch_rejected(tiny_problem: Problem) -> None:
    plan = RoutePlan(
        instance="TINY",
        solver="test",
        routes=[[1, 2, 3], [4, 5]],
        total_distance=100.0,
        n_vehicles=3,
    )
    with pytest.raises(ValueError, match="n_vehicles"):
        plan.validate_against(tiny_problem)


_PARTITION = st.lists(st.integers(min_value=0, max_value=5), min_size=0, max_size=12).filter(
    lambda xs: sorted(xs) != [1, 2, 3, 4, 5]
)


@given(_PARTITION)
def test_any_non_exact_partition_rejected(route: list[int]) -> None:
    """Property: a single route that is not exactly customers 1..5 must fail."""
    problem = parse_solomon(TINY_INSTANCE, name="TINY")
    plan = _plan([route])
    with pytest.raises(ValueError):
        plan.validate_against(problem)


def test_problem_rejects_non_zero_based_ids(tiny_problem: Problem) -> None:
    customers = [c.model_copy() for c in tiny_problem.customers]
    customers[1] = customers[1].model_copy(update={"id": 7})
    with pytest.raises(ValueError, match="consecutive range"):
        Problem(name="BAD", customers=customers, vehicle_capacity=tiny_problem.vehicle_capacity)
