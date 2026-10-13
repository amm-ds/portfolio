"""Tuning-stage tests: HPO determinism, acceptance modes, convergence traces."""

import importlib.util
import itertools
from pathlib import Path

import pytest
from routing_optimization.config import VRPConfig
from routing_optimization.parser import parse_solomon
from routing_optimization.solver import (
    clarke_wright_savings,
    nearest_neighbor,
    randomized,
    two_opt,
)
from routing_optimization.tuning import restart_plans, run_hpo

_spec = importlib.util.spec_from_file_location(
    "routing_tiny_instance", Path(__file__).parent / "tiny_instance.py"
)
assert _spec is not None and _spec.loader is not None
_tiny_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tiny_module)
TINY_INSTANCE = _tiny_module.TINY_INSTANCE


def _tiny(name: str):
    return parse_solomon(TINY_INSTANCE, name=name)


def _bases(problem):
    nn = nearest_neighbor(problem)
    cw = clarke_wright_savings(problem)
    return min((nn, cw), key=lambda p: p.total_distance)


def test_hpo_is_deterministic() -> None:
    """Same seed → same chosen config and same objective (restarts included)."""
    problems = [_tiny("T1"), _tiny("T2")]
    bases = {p.name: _bases(p) for p in problems}
    cfg = VRPConfig(
        seed=42,
        hpo_trials=8,
        hpo_budget_choices=[50, 100],
        hpo_restart_choices=[1, 2],
    )
    first = run_hpo(problems, bases, cfg)
    second = run_hpo(problems, bases, cfg)
    assert first.tuning == second.tuning
    assert first.best.mean_distance == second.best.mean_distance
    assert len(first.trials) == 8


def test_hpo_respects_search_space() -> None:
    problems = [_tiny("T1")]
    bases = {p.name: _bases(p) for p in problems}
    cfg = VRPConfig(seed=42, hpo_trials=6, hpo_restart_choices=[1, 2])
    result = run_hpo(problems, bases, cfg)
    assert result.tuning.max_iterations in cfg.hpo_budget_choices
    assert result.tuning.restarts in cfg.hpo_restart_choices
    assert result.tuning.acceptance in cfg.hpo_acceptance_choices
    assert result.tuning.tail_exchange in cfg.hpo_tail_exchange_choices


def test_restart_plans_are_seeded_and_distinct() -> None:
    problem = _tiny("T1")
    a = restart_plans(problem, seed=42, restarts=2)
    b = restart_plans(problem, seed=42, restarts=2)
    assert [p.routes for p in a] == [p.routes for p in b]  # deterministic
    assert a[0].routes != a[1].routes  # different seeds → different orders
    for plan in a:
        plan.validate_against(problem)


def test_best_acceptance_no_worse_than_first() -> None:
    problem = _tiny("T1")
    base = _bases(problem)
    first = two_opt(problem, base, max_iterations=200, acceptance="first")
    best = two_opt(problem, base, max_iterations=200, acceptance="best")
    assert best.total_distance <= first.total_distance + 1e-9


def test_tail_exchange_helps() -> None:
    problem = _tiny("T1")
    base = _bases(problem)
    with_tails = two_opt(problem, base, max_iterations=200, tail_exchange=True)
    without = two_opt(problem, base, max_iterations=200, tail_exchange=False)
    assert with_tails.total_distance <= without.total_distance + 1e-9


def test_two_opt_trace_records_convergence() -> None:
    problem = _tiny("T1")
    start = randomized(problem, seed=1)  # a poor start guarantees improvement moves
    trace: list[float] = []
    plan = two_opt(problem, start, max_iterations=200, trace=trace)
    assert trace[0] == pytest.approx(start.total_distance)  # construction start
    assert len(trace) >= 2  # at least one accepted move
    assert trace[-1] == pytest.approx(plan.total_distance)
    assert all(later <= earlier + 1e-9 for earlier, later in itertools.pairwise(trace))  # monotone
