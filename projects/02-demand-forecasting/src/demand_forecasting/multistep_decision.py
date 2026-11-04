"""Order-up-to policy simulation and the newsvendor order-quantile cost layer.

Documented cost assumptions, no savings claims; orders are forecast-
distribution quantiles calibrated on the selection origins, costed against
the scored test cells.
"""

from typing import Any

import numpy as np

from demand_forecasting.config import ForecastConfig
from demand_forecasting.multistep_constants import (
    CHAMPION,
    FLOOR,
    NEWSVENDOR_HOLDING_COST,
    NEWSVENDOR_STOCKOUT_COST,
)
from demand_forecasting.multistep_metrics import (
    _ladder_quantile,
    _paired_bootstrap_cost,
    order_up_to_cost,
)
from demand_forecasting.multistep_models import OriginScore
from demand_forecasting.multistep_routing import _routed_pred

# ---------------------------------------------------------------------------
# Decision metric: order-up-to policy simulation
# ---------------------------------------------------------------------------


def _policy_residuals(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    h: int,
    class_mask: np.ndarray,
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    policy: str,
) -> np.ndarray:
    """Selection-origin residuals (actual - forecast) for one policy, one class.

    The class mask is per SERIES; residuals are pooled over selection origins.
    """
    j = horizons.index(h)
    res: list[np.ndarray] = []
    for o in selection:
        sc = by_origin[o]
        if policy == "champion":
            pred = _routed_pred(sc, j, sparse, method_of)
        else:
            pred = sc.preds["seasonal_naive"][:, j]
        res.append((units[o + h] - pred)[class_mask])
    return np.concatenate(res)


def _newsvendor(
    dates: np.ndarray,
    cells: dict[str, Any],
    units: np.ndarray,
    sparse: np.ndarray,
    config: ForecastConfig,
) -> dict[str, Any]:
    """Newsvendor order-quantile cost layer (wave 22, additive in the decision
    block; documented cost assumptions — NOT a measured saving).

    For each service level q in ``config.service_levels`` and each scored
    cell (series x test origin x horizon day):

    - **routed policy order** — the routed band's q-quantile. Dense rows:
      linear interpolation of the committed p10/p50/p90 learner band ladder
      (extrapolation above p90 with the p50→p90 slope, zero-clipped — see
      :func:`_ladder_quantile`). Sparse rows: the q-quantile of the training
      history up to the origin (the existing sparse ladder machinery; the
      P(sale) summary stays in the bands block).
    - **floor policy order** — the q-quantile of the seasonal-naive empirical
      distribution: the training-window demand observed on the target day's
      weekday (0 when the weekday never occurred in the window).
    - **cost per cell** — holding 1.0 per ordered-but-unsold unit + stockout
      3.0 per unmet unit (per day, assumption).

    Reported per demand class as expected daily cost per unit-demand (total
    cost / total demand) for the routed vs the floor policy, with a paired
    cluster bootstrap CI on the difference (series resampled with
    replacement, one shared draw per replication).
    """
    dows = np.array([d.weekday() for d in dates.astype("datetime64[D]").astype(object)])
    out: dict[str, Any] = {
        "simulation": True,
        "label": "newsvendor order-quantile cost — documented cost assumptions, no savings claims",
        "cost_assumptions": {
            "holding_cost_per_unit_ordered_unsold_per_day": NEWSVENDOR_HOLDING_COST,
            "stockout_cost_per_unit_short_per_day": NEWSVENDOR_STOCKOUT_COST,
            "cost_basis": "per scored cell (series x test origin x horizon day); "
            "assumption, not measured",
        },
        "order_definition": {
            "routed_dense": "q-quantile of the committed p10/p50/p90 learner band ladder "
            "(linear interpolation; linear extrapolation above p90), zero-clipped",
            "routed_sparse": "q-quantile of the training history up to the origin (the "
            "existing sparse ladder machinery)",
            "floor": "q-quantile of the seasonal-naive empirical distribution: the "
            "training-window demand on the target day's weekday",
        },
        "service_levels": [float(q) for q in config.service_levels],
        "per_class": {},
    }
    for cls in [str(c) for c in np.unique(cells["class"])]:
        mask = cells["class"] == cls
        idx = np.flatnonzero(mask)
        ser = cells["series"][idx]
        org = cells["origin"][idx]
        h_of = cells["h"][idx]
        y = cells["y"][idx]
        per_q: dict[str, Any] = {}
        for q in config.service_levels:
            # routed orders: dense rows interpolate the band ladder; sparse
            # rows read the history ladder (one quantile per series x origin)
            order_r = np.empty(idx.size)
            dense_rows = ~sparse[ser]
            order_r[dense_rows] = _ladder_quantile(
                q,
                cells["p10"][idx[dense_rows]],
                cells["p50"][idx[dense_rows]],
                cells["p90"][idx[dense_rows]],
            )
            for k in np.flatnonzero(~dense_rows):
                order_r[k] = float(np.quantile(units[: int(org[k]) + 1, int(ser[k])], q))
            # floor orders: weekday-filtered training history quantile
            order_f = np.empty(idx.size)
            for r in range(idx.size):
                o = int(org[r])
                hist = units[: o + 1, int(ser[r])]
                same_dow = hist[dows[: o + 1] == dows[o + int(h_of[r])]]
                order_f[r] = float(np.quantile(same_dow, q)) if same_dow.size else 0.0
            cost_r = NEWSVENDOR_HOLDING_COST * np.maximum(order_r - y, 0.0) + (
                NEWSVENDOR_STOCKOUT_COST * np.maximum(y - order_r, 0.0)
            )
            cost_f = NEWSVENDOR_HOLDING_COST * np.maximum(order_f - y, 0.0) + (
                NEWSVENDOR_STOCKOUT_COST * np.maximum(y - order_f, 0.0)
            )
            denom = float(y.sum())
            per_q[f"q_{q:.2f}"] = {
                "routed_cost_per_unit_demand": float(cost_r.sum() / denom)
                if denom > 0
                else float("nan"),
                "floor_cost_per_unit_demand": float(cost_f.sum() / denom)
                if denom > 0
                else float("nan"),
                "routed_minus_floor": _paired_bootstrap_cost(
                    cost_r, cost_f, y, ser, config.bootstrap_reps, config.seed + 9602
                ),
            }
        out["per_class"][cls] = per_q
    return out


def _order_up_to(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    cells: dict[str, Any],
    class_of_series: np.ndarray,
    config: ForecastConfig,
    dates: np.ndarray,
) -> dict[str, Any]:
    """Order-up-to policy evaluation (simulation — no savings claims).

    Per series, service level τ: the order for (origin, h) is the τ-quantile
    of the policy's forecast distribution, approximated as
    ``point + q_τ(residuals)`` with residuals calibrated per (class, h) on the
    SELECTION origins. Cost per cell: ``holding · max(order - actual, 0) +
    stockout · max(actual - order, 0)``, summed over the scored test cells.
    Champion (routed) policy vs seasonal-naive policy, per demand class.
    """
    classes = [str(c) for c in np.unique(cells["class"])]
    out: dict[str, Any] = {
        "simulation": True,
        "label": "order-up-to policy simulation — cost assumptions documented, no savings claims",
        "cost_assumptions": {
            "holding_cost_per_unit": config.holding_cost,
            "stockout_cost_per_unit_short": config.stockout_cost,
            "cost_basis": "per scored cell (series x test origin x horizon)",
        },
        "service_levels": list(config.service_levels),
        "per_class": {},
    }
    for cls in classes:
        class_mask = class_of_series == cls  # per-series mask
        per_tau: dict[str, Any] = {}
        for tau in config.service_levels:
            totals: dict[str, float] = {}
            for policy in ("champion", "floor"):
                cost = 0.0
                demand = 0.0
                pred_key = CHAMPION if policy == "champion" else FLOOR
                for h in horizons:
                    cell_mask = (cells["h"] == h) & (cells["class"] == cls)
                    pred = cells["pred"][pred_key][cell_mask]
                    res = _policy_residuals(
                        by_origin,
                        selection,
                        horizons,
                        h,
                        class_mask,
                        units,
                        sparse,
                        method_of,
                        policy,
                    )
                    q_tau = float(np.quantile(res, tau))
                    order = np.maximum(pred + q_tau, 0.0)
                    y = cells["y"][cell_mask]
                    cost += order_up_to_cost(order, y, config.holding_cost, config.stockout_cost)
                    demand += float(y.sum())
                totals[policy] = cost
                totals[f"{policy}_per_unit_demand"] = cost / demand if demand > 0 else float("nan")
            per_tau[f"tau_{tau:.2f}"] = {
                **totals,
                "delta_champion_minus_floor": totals["champion"] - totals["floor"],
            }
        out["per_class"][cls] = per_tau
    # wave 22: the newsvendor order-quantile layer, additive over the
    # order-up-to simulation above (different order rule, documented costs)
    out["newsvendor"] = _newsvendor(dates, cells, units, sparse, config)
    return out
