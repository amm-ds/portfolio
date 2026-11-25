"""Fluid deterministic upper bound solved as a sparse linear program."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import linprog  # type: ignore[import-untyped]
from scipy.sparse import csr_matrix, vstack  # type: ignore[import-untyped]

from dynamic_pricing.calibrate import SeriesCalibration
from dynamic_pricing.env import HORIZON, MULTIPLIERS


@dataclass(frozen=True)
class FluidSolution:
    """Optimal time-price mixtures and normalised profit including salvage."""

    profit: float
    action_shares: NDArray[np.float64]
    expected_sales: float


def solve_fluid_lp(
    calibration: SeriesCalibration,
    epsilon: float,
    reference_demand: ArrayLike,
    inventory: int,
    revenue_reference: float,
    allowed_actions: ArrayLike | None = None,
) -> FluidSolution:
    """Solve the remaining-horizon fluid relaxation with known elasticity.

    Each variable is the share of one day assigned to one ladder price. Daily
    mixture weights sum to at most one, so exhausted inventory can idle later
    days. Expected sales cannot exceed inventory, and the objective includes
    salvage on expected unsold inventory.
    """
    reference = np.asarray(reference_demand, dtype=np.float64)
    if reference.ndim != 1 or reference.size == 0:
        raise ValueError("reference_demand must be a non-empty vector")
    if inventory < 0 or revenue_reference <= 0:
        raise ValueError("inventory must be non-negative and revenue_reference positive")
    n_days = reference.size
    n_actions = len(MULTIPLIERS)
    demand = reference[:, None] * np.power(MULTIPLIERS[None, :], epsilon)
    prices = MULTIPLIERS * calibration.p_ref
    cost = 0.60 * calibration.p_ref
    salvage = 0.30 * calibration.p_ref
    net_profit = ((prices[None, :] - cost - salvage) * demand) / revenue_reference

    rows = np.repeat(np.arange(n_days), n_actions)
    columns = np.arange(n_days * n_actions)
    daily_mixtures = csr_matrix(
        (np.ones(n_days * n_actions), (rows, columns)),
        shape=(n_days, n_days * n_actions),
    )
    inventory_constraint = csr_matrix(demand.reshape(1, -1))
    bounds = [(0.0, 1.0)] * (n_days * n_actions)
    if allowed_actions is not None:
        mask = np.asarray(allowed_actions, dtype=np.bool_)
        if mask.shape != (n_actions,) or not mask.any():
            raise ValueError("allowed_actions must contain at least one of the seven actions")
        bounds[:n_actions] = [(0.0, float(allowed)) for allowed in mask]

    result = linprog(
        c=-net_profit.ravel(),
        A_ub=vstack([daily_mixtures, inventory_constraint], format="csr"),
        b_ub=np.concatenate((np.ones(n_days), np.array([float(inventory)]))),
        bounds=bounds,
        method="highs",
    )
    if not result.success or result.x is None:
        raise RuntimeError(f"fluid LP failed: {result.message}")
    shares = np.asarray(result.x, dtype=np.float64).reshape(n_days, n_actions)
    expected_sales = float(np.sum(shares * demand))
    profit = salvage * inventory / revenue_reference - float(result.fun)
    return FluidSolution(profit=profit, action_shares=shares, expected_sales=expected_sales)


def fluid_upper_bound(
    calibration: SeriesCalibration, epsilon: float, rho: float, horizon: int = HORIZON
) -> float:
    """Return the full-episode fluid upper bound for one known spec."""
    dow = np.asarray(calibration.dow, dtype=np.float64)
    reference = calibration.base * dow[np.arange(horizon) % 7]
    inventory = max(1, round(float(reference.sum()) / rho))
    revenue_reference = float(reference.sum()) * calibration.p_ref
    return solve_fluid_lp(calibration, epsilon, reference, inventory, revenue_reference).profit
