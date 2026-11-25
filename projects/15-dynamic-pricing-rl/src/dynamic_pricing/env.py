"""Constrained Gymnasium pricing environment with common random numbers."""

from dataclasses import dataclass
from typing import Any, cast

import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, Discrete, Space
from numpy.typing import NDArray
from scipy.stats import nbinom  # type: ignore[import-untyped]

from dynamic_pricing.calibrate import SeriesCalibration

MULTIPLIERS = np.array([0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30], dtype=np.float64)
HORIZON = 91
HISTORY_LEN = 14
OBSERVATION_LEN = 4 + 2 * HISTORY_LEN + 7


@dataclass(frozen=True)
class EpisodeSpec:
    """Complete exogenous definition of one reproducible episode."""

    series_id: str
    epsilon: float
    rho: float
    seed: int


class PricingEnv(gym.Env[NDArray[np.float32], int]):
    """Ninety-one-day single-product inventory pricing with masked actions."""

    metadata = {"render_modes": []}  # noqa: RUF012 - Gymnasium defines an instance attribute.

    def __init__(
        self,
        calibrations: dict[str, SeriesCalibration],
        *,
        strict: bool = False,
        horizon: int = HORIZON,
        zero_noise: bool = False,
    ) -> None:
        super().__init__()
        if not calibrations:
            raise ValueError("at least one calibration is required")
        if horizon <= 0:
            raise ValueError("horizon must be positive")
        self.calibrations = calibrations
        self.strict = strict
        self.horizon = horizon
        self.zero_noise = zero_noise
        self.action_space = cast(Space[int], Discrete(len(MULTIPLIERS)))
        self.observation_space = Box(
            low=-np.inf, high=np.inf, shape=(OBSERVATION_LEN,), dtype=np.float32
        )
        self._spec: EpisodeSpec | None = None
        self._calibration: SeriesCalibration | None = None
        self._day = 0
        self._current_action = 3
        self._last_change_day: int | None = None
        self._initial_inventory = 0
        self._inventory = 0
        self._violations = 0
        self._gross_profit = 0.0
        self._normalised_gross_profit = 0.0
        self._revenue_reference = 1.0
        self._reference_demand = np.zeros(horizon, dtype=np.float64)
        self._uniforms = np.zeros((horizon, len(MULTIPLIERS)), dtype=np.float64)
        self._demand = np.zeros((horizon, len(MULTIPLIERS)), dtype=np.int64)
        self._history = np.zeros((HISTORY_LEN, 2), dtype=np.float64)

    @property
    def day(self) -> int:
        return self._day

    @property
    def current_action(self) -> int:
        return self._current_action

    @property
    def inventory(self) -> int:
        return self._inventory

    @property
    def initial_inventory(self) -> int:
        return self._initial_inventory

    @property
    def violations(self) -> int:
        return self._violations

    @property
    def reference_demand(self) -> NDArray[np.float64]:
        return self._reference_demand.copy()

    @property
    def demand_uniforms(self) -> NDArray[np.float64]:
        return self._uniforms.copy()

    @property
    def episode_spec(self) -> EpisodeSpec:
        if self._spec is None:
            raise RuntimeError("reset with an EpisodeSpec first")
        return self._spec

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[NDArray[np.float32], dict[str, Any]]:
        """Start the supplied spec; a spec-less reset repeats the current episode.

        Repeating the current spec supports Gymnasium and SB3 reset checks without
        introducing a second, implicit way to construct an episode.
        """
        super().reset(seed=seed)
        supplied = None if options is None else options.get("spec")
        if supplied is None:
            if self._spec is None:
                raise ValueError("reset requires options={'spec': EpisodeSpec(...)}")
        elif isinstance(supplied, EpisodeSpec):
            self._spec = supplied
        else:
            raise TypeError("options['spec'] must be an EpisodeSpec")
        spec = self.episode_spec
        if spec.series_id not in self.calibrations:
            raise KeyError(f"unknown series_id: {spec.series_id}")
        if not -5.0 <= spec.epsilon <= -0.8:
            raise ValueError("epsilon must lie in the pre-registered truncated prior")
        if spec.rho not in {0.7, 1.0, 1.3}:
            raise ValueError("rho must be one of 0.7, 1.0, 1.3")

        self._calibration = self.calibrations[spec.series_id]
        calibration = self._calibration
        dow = np.asarray(calibration.dow, dtype=np.float64)
        self._reference_demand = calibration.base * dow[np.arange(self.horizon) % 7]
        self._initial_inventory = max(1, round(float(self._reference_demand.sum()) / spec.rho))
        self._inventory = self._initial_inventory
        self._revenue_reference = float(self._reference_demand.sum()) * calibration.p_ref
        self._day = 0
        self._current_action = 3
        self._last_change_day = None
        self._violations = 0
        self._gross_profit = 0.0
        self._normalised_gross_profit = 0.0
        self._history.fill(0.0)

        rng = np.random.default_rng(spec.seed)
        self._uniforms = rng.random((self.horizon, len(MULTIPLIERS)))
        self._uniforms = np.clip(self._uniforms, 1e-12, 1.0 - 1e-12)
        means = self._reference_demand[:, None] * np.power(MULTIPLIERS[None, :], spec.epsilon)
        if self.zero_noise:
            self._demand = np.floor(means).astype(np.int64)
        else:
            probabilities = calibration.k / (calibration.k + means)
            self._demand = np.asarray(
                nbinom.ppf(self._uniforms, calibration.k, probabilities), dtype=np.int64
            )
        return self._observation(), {"violations": 0}

    def _observation(self) -> NDArray[np.float32]:
        calibration = self._calibration
        if calibration is None:
            raise RuntimeError("reset with an EpisodeSpec first")
        days_since_change = (
            7 if self._last_change_day is None else self._day - self._last_change_day
        )
        next_profile = np.asarray(calibration.dow)[(self._day + 1 + np.arange(7)) % 7]
        observation = np.concatenate(
            (
                np.array(
                    [
                        self._day / self.horizon,
                        self._inventory / self._initial_inventory,
                        days_since_change / 7.0,
                        MULTIPLIERS[self._current_action],
                    ]
                ),
                self._history.ravel(),
                next_profile,
            )
        )
        return np.asarray(observation, dtype=np.float32)

    def action_masks(self) -> NDArray[np.bool_]:
        """Mask C1-C3: ladder band, one-step changes, seven-day cooldown."""
        if self._spec is None:
            raise RuntimeError("reset with an EpisodeSpec first")
        mask = np.zeros(len(MULTIPLIERS), dtype=np.bool_)
        for action in range(len(MULTIPLIERS)):
            change = action - self._current_action
            one_step = abs(change) <= 1
            cooldown = (
                change == 0
                or self._last_change_day is None
                or self._day - self._last_change_day >= 7
            )
            mask[action] = one_step and cooldown
        return mask

    def _invalid_action(self, action: int) -> int:
        self._violations += 1
        if self.strict:
            raise ValueError(f"invalid masked action {action} at day {self._day}")
        return self._current_action

    def step(self, action: int) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        if self._spec is None or self._calibration is None:
            raise RuntimeError("reset with an EpisodeSpec first")
        if self._day >= self.horizon:
            raise RuntimeError("episode is terminated; reset before another step")
        if not self.action_space.contains(action):
            action = self._invalid_action(int(action))
        elif not self.action_masks()[action]:
            action = self._invalid_action(action)

        previous_action = self._current_action
        if action != previous_action:
            self._last_change_day = self._day
        self._current_action = action

        multiplier = float(MULTIPLIERS[action])
        price = multiplier * self._calibration.p_ref
        demand = int(self._demand[self._day, action])
        sales = min(demand, self._inventory)
        self._inventory -= sales
        gross_profit = (price - 0.60 * self._calibration.p_ref) * sales
        self._gross_profit += gross_profit
        self._normalised_gross_profit += gross_profit / self._revenue_reference
        reward = gross_profit / self._revenue_reference

        reference = float(self._reference_demand[self._day])
        self._history = np.roll(self._history, shift=-1, axis=0)
        self._history[-1] = (multiplier, sales / reference)
        self._day += 1
        terminated = self._day == self.horizon
        salvage = 0.0
        if terminated:
            salvage = 0.30 * self._calibration.p_ref * self._inventory
            reward += salvage / self._revenue_reference
        info: dict[str, Any] = {
            "violations": self._violations,
            "sales": sales,
            "inventory": self._inventory,
            "price": price,
            "multiplier": multiplier,
            "lambda_ref": reference,
            "gross_profit": self._gross_profit,
            "normalised_gross_profit": self._normalised_gross_profit,
            "salvage": salvage,
        }
        return self._observation(), float(reward), terminated, False, info
