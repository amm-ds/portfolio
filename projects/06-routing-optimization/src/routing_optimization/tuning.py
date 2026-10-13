"""Seeded hyperparameter search for the improvement stage (no new deps).

A small random search (Optuna-style, but stdlib-only and fully deterministic):
each trial samples a :class:`~routing_optimization.schemas.TwoOptTuning` from
the configured discrete search space and evaluates it as the mean improved
distance across every instance. Constructions (nearest neighbor,
Clarke-Wright, and the seeded randomized restarts) are computed once and
reused by all trials, so the whole search costs well under a second.
"""

import random
from dataclasses import dataclass, field

from portfolio_core.logging import get_logger

from routing_optimization.config import VRPConfig
from routing_optimization.schemas import Problem, RoutePlan, TwoOptTuning
from routing_optimization.solver import two_opt

logger = get_logger(__name__)


@dataclass(frozen=True)
class HpoTrial:
    """One evaluated configuration of the improvement stage."""

    tuning: TwoOptTuning
    mean_distance: float


@dataclass
class HpoResult:
    """Outcome of the search: the winning config plus all evaluated trials."""

    best: HpoTrial
    trials: list[HpoTrial] = field(default_factory=list)

    @property
    def tuning(self) -> TwoOptTuning:
        """The chosen improvement-stage configuration."""
        return self.best.tuning


def restart_plans(problem: Problem, seed: int, restarts: int) -> list[RoutePlan]:
    """Randomized constructions for seeds ``seed .. seed + restarts - 1``.

    Imported lazily to avoid a module-level cycle with ``solver``.
    """
    from routing_optimization.solver import randomized

    return [randomized(problem, seed=seed + i) for i in range(restarts)]


def best_start(base: RoutePlan, restarts: list[RoutePlan]) -> RoutePlan:
    """Cheapest starting plan: the better construction or a restart survivor."""
    return min([base, *restarts], key=lambda p: p.total_distance)


def evaluate_tuning(
    problems: list[Problem],
    bases: dict[str, RoutePlan],
    restarts_cache: dict[str, list[RoutePlan]],
    tuning: TwoOptTuning,
) -> float:
    """Mean improved distance of ``tuning`` across instances (the objective)."""
    total = 0.0
    for problem in problems:
        name = problem.name
        restarts = restarts_cache[name][: tuning.restarts]
        start = best_start(bases[name], restarts)
        plan = two_opt(
            problem,
            start,
            max_iterations=tuning.max_iterations,
            acceptance=tuning.acceptance,
            tail_exchange=tuning.tail_exchange,
        )
        total += plan.total_distance
    return total / len(problems)


def run_hpo(
    problems: list[Problem],
    bases: dict[str, RoutePlan],
    cfg: VRPConfig,
) -> HpoResult:
    """Seeded random search over the improvement-stage search space.

    The RNG is seeded with ``cfg.seed``; sampling, evaluation order and tie
    handling are deterministic, so the chosen config is reproducible.
    """
    max_restarts = max(cfg.hpo_restart_choices)
    restarts_cache = {
        p.name: restart_plans(p, seed=cfg.seed, restarts=max_restarts) for p in problems
    }

    rng = random.Random(cfg.seed)
    result = HpoResult(best=HpoTrial(TwoOptTuning(), float("inf")))
    for _ in range(cfg.hpo_trials):
        tuning = TwoOptTuning(
            max_iterations=rng.choice(cfg.hpo_budget_choices),
            acceptance=rng.choice(cfg.hpo_acceptance_choices),
            tail_exchange=rng.choice(cfg.hpo_tail_exchange_choices),
            restarts=rng.choice(cfg.hpo_restart_choices),
        )
        mean = evaluate_tuning(problems, bases, restarts_cache, tuning)
        trial = HpoTrial(tuning, mean)
        result.trials.append(trial)
        if mean < result.best.mean_distance:  # strict: first best wins ties
            result.best = trial
        logger.info("hpo trial: %-55s mean=%.2f", tuning.summary(), mean)
    logger.info("hpo chose: %s (mean %.2f)", result.tuning.summary(), result.best.mean_distance)
    return result
