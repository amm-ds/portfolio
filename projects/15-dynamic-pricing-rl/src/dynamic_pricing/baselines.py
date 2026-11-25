"""Non-RL pricing baselines B0-B3 and their masked episode runner."""

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from dynamic_pricing.bound import solve_fluid_lp
from dynamic_pricing.env import EpisodeSpec, PricingEnv


class Baseline(Protocol):
    policy_id: str

    def reset(self, seed: int) -> None: ...

    def act(self, env: PricingEnv) -> int: ...

    def observe(self, info: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class EpisodeResult:
    policy_id: str
    spec: EpisodeSpec
    mean_normalised_profit: float
    raw_gross_profit: float
    violations: int
    terminal_inventory: int


class FixedBaseline:
    """B0 (reference) or B1 (one tuned static target), reached via valid steps."""

    def __init__(self, target_action: int) -> None:
        if not 0 <= target_action <= 6:
            raise ValueError("target_action must be on the seven-step ladder")
        self.target_action = target_action
        self.policy_id = "B0" if target_action == 3 else "B1"

    def reset(self, seed: int) -> None:
        del seed

    def act(self, env: PricingEnv) -> int:
        direction = int(np.sign(self.target_action - env.current_action))
        candidate = env.current_action + direction
        return candidate if env.action_masks()[candidate] else env.current_action

    def observe(self, info: dict[str, Any]) -> None:
        del info


class MarkdownBaseline:
    """B2 sell-through rule with fixed percentage thresholds."""

    policy_id = "B2"

    def __init__(self, behind_pct: float, ahead_pct: float) -> None:
        self.behind_pct = behind_pct
        self.ahead_pct = ahead_pct
        self.cumulative_sales = 0

    def reset(self, seed: int) -> None:
        del seed
        self.cumulative_sales = 0

    def act(self, env: PricingEnv) -> int:
        plan = env.initial_inventory * env.day / env.horizon
        candidate = env.current_action
        if plan > 0 and self.cumulative_sales < plan * (1.0 - self.behind_pct / 100.0):
            candidate -= 1
        elif self.cumulative_sales > plan * (1.0 + self.ahead_pct / 100.0):
            candidate += 1
        candidate = int(np.clip(candidate, 0, 6))
        return candidate if env.action_masks()[candidate] else env.current_action

    def observe(self, info: dict[str, Any]) -> None:
        self.cumulative_sales += int(info["sales"])


class ThompsonBaseline:
    """B3 conjugate elasticity posterior plus a sampled remaining fluid LP."""

    policy_id = "B3"

    def __init__(
        self,
        prior_mean: float = -2.5,
        prior_sd: float = 0.8,
        observation_sd: float = 0.35,
    ) -> None:
        if prior_sd <= 0 or observation_sd <= 0:
            raise ValueError("prior_sd and observation_sd must be positive")
        self.prior_mean = prior_mean
        self.prior_sd = prior_sd
        self.observation_sd = observation_sd
        self._precision = 1.0 / prior_sd**2
        self._scaled_mean = self.prior_mean * self._precision
        self._rng = np.random.default_rng(42)

    @property
    def posterior_mean(self) -> float:
        return self._scaled_mean / self._precision

    def reset(self, seed: int) -> None:
        self._precision = 1.0 / self.prior_sd**2
        self._scaled_mean = self.prior_mean * self._precision
        self._rng = np.random.default_rng(seed)

    def act(self, env: PricingEnv) -> int:
        posterior_sd = float(np.sqrt(1.0 / self._precision))
        epsilon = float(np.clip(self._rng.normal(self.posterior_mean, posterior_sd), -5.0, -0.8))
        spec = env.episode_spec
        calibration = env.calibrations[spec.series_id]
        reference = env.reference_demand
        revenue_reference = float(reference.sum()) * calibration.p_ref
        mask = env.action_masks()
        solution = solve_fluid_lp(
            calibration,
            epsilon,
            reference[env.day :],
            env.inventory,
            revenue_reference,
            allowed_actions=mask,
        )
        allowed_shares = np.where(mask, solution.action_shares[0], -np.inf)
        return int(np.argmax(allowed_shares))

    def observe(self, info: dict[str, Any]) -> None:
        log_multiplier = float(np.log(float(info["multiplier"])))
        if log_multiplier == 0.0:
            return
        response = float(np.log((float(info["sales"]) + 0.5) / float(info["lambda_ref"])))
        self._precision += log_multiplier**2 / self.observation_sd**2
        self._scaled_mean += log_multiplier * response / self.observation_sd**2


def make_baseline(
    policy_id: str,
    *,
    b1_action: int = 3,
    b2_behind_pct: float = 10.0,
    b2_ahead_pct: float = 10.0,
    prior_mean: float = -2.5,
    prior_sd: float = 0.8,
    observation_sd: float = 0.35,
) -> Baseline:
    if policy_id == "B0":
        return FixedBaseline(3)
    if policy_id == "B1":
        return FixedBaseline(b1_action)
    if policy_id == "B2":
        return MarkdownBaseline(b2_behind_pct, b2_ahead_pct)
    if policy_id == "B3":
        return ThompsonBaseline(prior_mean, prior_sd, observation_sd)
    raise ValueError(f"unknown baseline: {policy_id}")


def run_baseline(env: PricingEnv, spec: EpisodeSpec, policy: Baseline) -> EpisodeResult:
    """Run one episode and reject any policy action forbidden by the mask."""
    env.reset(options={"spec": spec})
    policy.reset(spec.seed)
    total_profit = 0.0
    while True:
        action = policy.act(env)
        if not env.action_masks()[action]:
            raise ValueError(f"{policy.policy_id} returned masked action {action}")
        _, reward, terminated, _, info = env.step(action)
        policy.observe(info)
        total_profit += reward
        if terminated:
            return EpisodeResult(
                policy_id=policy.policy_id,
                spec=spec,
                mean_normalised_profit=total_profit,
                raw_gross_profit=float(info["gross_profit"]),
                violations=int(info["violations"]),
                terminal_inventory=int(info["inventory"]),
            )
