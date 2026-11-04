"""Selection-origin calibration: peak-weight choice, hurdle zero-correction,
per-series routing (MAE and cost-aware), convex ensemble, routed accessor.

Everything here picks a mapping, weight or method on the SELECTION origins
only and applies it to all origins; the test origins are never read
(property-tested).
"""

from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression

from demand_forecasting.config import ForecastConfig
from demand_forecasting.intermittent import STATISTICAL_METHODS
from demand_forecasting.multistep_constants import (
    ML_SPARSE,
    NEWSVENDOR_HOLDING_COST,
    NEWSVENDOR_STOCKOUT_COST,
)
from demand_forecasting.multistep_metrics import _paired_bootstrap_cost, _paired_bootstrap_mae
from demand_forecasting.multistep_models import PEAK_WEIGHTS, OriginScore

# Hurdle-family candidates that go through the selection-origin
# zero-correction (identity / scalar / isotonic) — all are two-stage
# p̂ x size models with the same conditional-mean bias structure.
HURDLE_CANDIDATES = ("hurdle_hgb", "hurdle_lgbm", "peak_weighted_hgb")


# ---------------------------------------------------------------------------
# Hurdle zero-correction (chosen on the SELECTION origins only)
# ---------------------------------------------------------------------------


def choose_peak_weight(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
) -> dict[str, Any]:
    """Pick the peak_weighted_hgb sample-weight multiplier on SELECTION cells.

    Both weight variants (see :data:`PEAK_WEIGHTS`) are fit at every origin;
    the one with the lowest pooled |error| over the selection origins' cells
    wins and its raw predictions become the ``peak_weighted_hgb`` candidate
    (which then goes through the same zero-correction as the other hurdle
    models). Reads no test-origin actual (property-tested).
    """
    scores: dict[str, float] = {}
    for w in PEAK_WEIGHTS:
        total = 0.0
        count = 0
        for o in selection:
            y = np.column_stack([units[o + h] for h in horizons])
            total += float(np.abs(by_origin[o].pw_raw[w] - y).sum())
            count += int(y.size)
        scores[str(w)] = total / count if count else float("nan")
    chosen = float(min(scores, key=lambda k: scores[k]))
    for sc in by_origin.values():
        sc.hurdle_raw["peak_weighted_hgb"] = sc.pw_raw[chosen]
        sc.preds["peak_weighted_hgb"] = sc.pw_raw[chosen].copy()
        # promote the same variant in the what-if shock entries (keyed by
        # weight until now; apply_hurdle_correction maps the promoted key)
        for entry in sc.shocked.values():
            key = f"peak_weighted_hgb@{chosen}"
            if key in entry:
                entry["peak_weighted_hgb"] = entry.pop(key)
                for w in PEAK_WEIGHTS:
                    entry.pop(f"peak_weighted_hgb@{w}", None)
    return {
        "weights": list(PEAK_WEIGHTS),
        "chosen": chosen,
        "selection_mae": scores,
        "definition": "pooled MAE of each raw weight variant over the selection origins' "
        "cells; the winner is applied to all origins (then zero-corrected)",
    }


def apply_hurdle_correction(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    candidates: tuple[str, ...] = HURDLE_CANDIDATES,
) -> dict[str, Any]:
    """Pick and apply the hurdle zero-correction — tested, not assumed.

    The raw hurdle point forecast (p̂ x size) is biased toward non-zero
    answers (it is a conditional mean of the positive part). For every
    hurdle-family candidate (see :data:`HURDLE_CANDIDATES`) three mappings are
    compared on the SELECTION origins' cells only: identity, a scalar
    ``Σactual / Σpred`` shrink, and an isotonic regression of actual on
    predicted. The mapping with the lowest summed |error| on the selection
    cells wins and is applied to EVERY origin's stored predictions (in place),
    so routing and scoring see the same corrected candidate. Reads no
    test-origin actual (property-tested). Returns, per candidate, the choice
    and the selection-origin MAE of every variant (the "does the correction
    help?" evidence, committed in metrics.json).
    """
    out: dict[str, Any] = {}
    for cand in candidates:
        raw_sel: list[np.ndarray] = []
        y_sel: list[np.ndarray] = []
        for o in selection:
            sc = by_origin[o]
            if cand not in sc.hurdle_raw:  # pragma: no cover - defensive
                raise ValueError(f"origin {o} has no raw {cand} predictions")
            # both flattened series-major so cell i of raw pairs with cell i of y
            raw_sel.append(np.transpose(sc.hurdle_raw[cand]).reshape(-1))
            y_sel.append(np.column_stack([units[o + h] for h in horizons]).reshape(-1))
        raw = np.concatenate(raw_sel)
        y = np.concatenate(y_sel)
        denom = float(raw.sum())
        scalar = float(y.sum()) / denom if denom > 0 else 1.0
        iso = IsotonicRegression(out_of_bounds="clip").fit(raw, y)
        variants: dict[str, np.ndarray] = {
            "identity": raw,
            "scalar": raw * scalar,
            "isotonic": np.asarray(iso.predict(raw), dtype=float),
        }
        maes = {name: float(np.abs(v - y).mean()) for name, v in variants.items()}
        chosen = min(maes, key=lambda name: maes[name])

        def _map(
            flat: np.ndarray,
            _chosen: str = chosen,
            _scalar: float = scalar,
            _iso: IsotonicRegression = iso,
        ) -> np.ndarray:
            if _chosen == "identity":
                return flat
            if _chosen == "scalar":
                return flat * _scalar
            return np.asarray(_iso.predict(flat), dtype=float)

        for sc in by_origin.values():
            if cand not in sc.hurdle_raw:  # pragma: no cover - defensive
                continue
            sc.preds[cand] = _map(sc.hurdle_raw[cand].reshape(-1)).reshape(
                sc.hurdle_raw[cand].shape
            )
            # the demo payload's what-if curves go through the same mapping
            for entry in sc.shocked.values():
                if cand in entry:
                    raw_s = entry[cand]
                    entry[cand] = _map(raw_s.reshape(-1)).reshape(raw_s.shape)
        out[cand] = {
            "chosen": chosen,
            "selection_mae": maes,
            "scalar_factor": scalar,
        }
    out["note"] = (
        "identity/scalar/isotonic compared on the selection origins only; the "
        "winner per hurdle candidate is applied to all origins; a series of "
        "all-zero training windows has no correction candidate (raw p̂=0)"
    )
    return out


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    n_series: int,
) -> np.ndarray:
    """Per-series method: best candidate on SELECTION origins only.

    Pool per series (the wave-20 extension of the wave-19 statistical-only
    router): sparse (ADI ≥ 1.32) series choose among the statistical methods
    AND the peak-capable ML candidates (hgb_tweedie / hurdle_hgb) — direct_hgb
    stays excluded there (the wave-19 finding: boosted trees overfit sparse
    series); smooth/erratic series choose among direct_hgb (the previous
    routed winner) and the two ML candidates. Property (tested): the choice
    reads no test-origin actual — shuffling the test window leaves every
    choice unchanged.
    """
    pool = (*STATISTICAL_METHODS, *ML_SPARSE, "direct_hgb")
    cand_err = {name: np.zeros(n_series) for name in pool}
    for o in selection:
        sc = by_origin[o]
        actual = np.column_stack([units[o + h] for h in horizons])
        for name in pool:
            cand_err[name] += np.abs(actual - sc.preds[name]).sum(axis=1)
    # eligibility: statistical methods are sparse-only, direct_hgb is dense-only
    for name in STATISTICAL_METHODS:
        cand_err[name][~sparse] = np.inf
    cand_err["direct_hgb"][sparse] = np.inf
    stack = np.stack([cand_err[name] for name in pool], axis=1)
    method_of = np.array(pool, dtype=object)[np.argmin(stack, axis=1)]
    return method_of.copy()


# ---------------------------------------------------------------------------
# Cost-aware routing (wave 23): same pools + eligibility, but the per-series
# pick minimises summed newsvendor cost at one service level on the SELECTION
# origins — the roadmap answer to "MAE-optimal routing can over-order at high
# service levels" (priced with the wave-22 cost assumptions, no savings claim)
# ---------------------------------------------------------------------------

# The service level the cost-aware router optimises (the wave-22 newsvendor
# layer showed q=0.90 is where the MAE-routed over-ordering shows up first).
COST_ROUTING_LEVEL = 0.90


def _selection_errors(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    pred_of: Any,
) -> np.ndarray:
    """Selection-origin residuals (actual - pred) stacked as (origin, series, h).

    ``pred_of`` maps one origin score to its full (series, h) prediction.
    """
    out = np.empty((len(selection), units.shape[1], len(horizons)))
    for k, o in enumerate(selection):
        actual = np.column_stack([units[o + h] for h in horizons])
        out[k] = actual - pred_of(by_origin[o])
    return out


def _routed_pred_of(method_of: np.ndarray) -> Any:
    """The per-series routed prediction (all horizons) for _selection_errors."""

    def pred(sc: OriginScore) -> np.ndarray:
        n_h = sc.preds["direct_hgb"].shape[1]
        return np.column_stack([_routed_pred(sc, j, method_of, method_of) for j in range(n_h)])

    return pred


def _route_cost(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    n_series: int,
) -> np.ndarray:
    """Per-series method chosen by summed newsvendor cost on SELECTION origins.

    The order for (origin, h) under method m is ``max(pred_m + q_level of
    that method's selection residuals for the series, 0)`` — one order-up-to
    quantile per series and method; the cost per cell is the documented
    wave-22 assumption (holding 1.0 per ordered-but-unsold unit, stockout 3.0
    per unmet unit). Pools and eligibility match :func:`_route`; the rule
    reads no test-origin actual (property-tested alongside the router).
    """
    pool = (*STATISTICAL_METHODS, *ML_SPARSE, "direct_hgb")
    n_h = len(horizons)
    resid = {name: np.empty((len(selection), n_series, n_h)) for name in pool}
    for k, o in enumerate(selection):
        sc = by_origin[o]
        actual = np.column_stack([units[o + h] for h in horizons])
        for name in pool:
            resid[name][k] = actual - sc.preds[name]
    cand_cost = {name: np.zeros(n_series) for name in pool}
    for name in pool:
        q = np.quantile(resid[name], COST_ROUTING_LEVEL, axis=(0, 2))  # (n_series,)
        for o in selection:
            actual = np.column_stack([units[o + h] for h in horizons])
            order = np.maximum(by_origin[o].preds[name] + q[:, None], 0.0)
            cand_cost[name] += (
                NEWSVENDOR_HOLDING_COST * np.maximum(order - actual, 0.0)
                + NEWSVENDOR_STOCKOUT_COST * np.maximum(actual - order, 0.0)
            ).sum(axis=1)
    for name in STATISTICAL_METHODS:
        cand_cost[name][~sparse] = np.inf
    cand_cost["direct_hgb"][sparse] = np.inf
    stack = np.stack([cand_cost[name] for name in pool], axis=1)
    return np.array(pool, dtype=object)[np.argmin(stack, axis=1)].copy()


def _routed_cells(
    by_origin: dict[int, OriginScore],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of_cost: np.ndarray,
) -> dict[str, Any]:
    """Minimal long table for the cost-routed arm (row order matches _test_cells)."""
    n_cells = units.shape[1] * len(test) * len(horizons)
    cells: dict[str, Any] = {
        "series": np.empty(n_cells, dtype=int),
        "origin": np.empty(n_cells, dtype=int),
        "h": np.empty(n_cells, dtype=int),
        "y": np.empty(n_cells),
        "pred": {"routed_cost": np.empty(n_cells)},
    }
    r = 0
    n = units.shape[1]
    for o in test:
        sc = by_origin[o]
        for j, h in enumerate(horizons):
            sl = slice(r, r + n)
            cells["series"][sl] = np.arange(n)
            cells["origin"][sl] = o
            cells["h"][sl] = h
            cells["y"][sl] = units[o + h]
            cells["pred"]["routed_cost"][sl] = _routed_pred(sc, j, sparse, method_of_cost)
            r += n
    return cells


def _arm_selection_cost(
    err: np.ndarray,
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
) -> float:
    """Total selection-origin newsvendor cost of one routing arm at
    :data:`COST_ROUTING_LEVEL` (the cost-aware rule's own objective)."""
    q = np.quantile(err, COST_ROUTING_LEVEL, axis=(0, 2))
    total = 0.0
    for k in range(len(selection)):
        actual = np.column_stack([units[o + h] for o in [selection[k]] for h in horizons])
        pred = actual - err[k]
        order = np.maximum(pred + q[:, None], 0.0)
        total += float(
            (
                NEWSVENDOR_HOLDING_COST * np.maximum(order - actual, 0.0)
                + NEWSVENDOR_STOCKOUT_COST * np.maximum(actual - order, 0.0)
            ).sum()
        )
    return total


def _cost_aware_block(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    method_of: np.ndarray,
    method_of_cost: np.ndarray,
    ca_cells: dict[str, Any],
    cells: dict[str, Any],
    class_of_series: np.ndarray,
    series_ids: list[str],
    config: ForecastConfig,
) -> dict[str, Any]:
    """The routing.cost_aware block: MAE + newsvendor-cost comparison of the
    cost-routed arm vs the MAE-routed champion on the scored test origins."""
    from collections import Counter

    y = ca_cells["y"]
    ser = ca_cells["series"]
    pred_mae = cells["pred"]["routed"]
    pred_cost = ca_cells["pred"]["routed_cost"]
    # ca_cells row order matches `cells` exactly (same origins/horizons order)
    overall = _paired_bootstrap_mae(
        pred_cost - y,
        pred_mae - y,
        ser,
        config.bootstrap_reps,
        config.seed + 9701,
    )
    # selection-origin residual stacks of both arms (test orders + self-check)
    sel_mae = _selection_errors(by_origin, selection, horizons, units, _routed_pred_of(method_of))
    sel_cost = _selection_errors(
        by_origin, selection, horizons, units, _routed_pred_of(method_of_cost)
    )
    selection_cost = {
        "routed": _arm_selection_cost(sel_mae, selection, horizons, units),
        "routed_cost": _arm_selection_cost(sel_cost, selection, horizons, units),
    }

    per_class: dict[str, Any] = {}
    for ci, cls in enumerate([str(c) for c in np.unique(class_of_series)]):
        mask_cls = class_of_series[ser] == cls
        idx = np.flatnonzero(mask_cls)
        mae_cls = _paired_bootstrap_mae(
            pred_cost[idx] - y[idx],
            pred_mae[idx] - y[idx],
            ser[idx],
            config.bootstrap_reps,
            config.seed + 9711 + ci,
        )
        per_q: dict[str, Any] = {}
        for q in config.service_levels:
            # test-cell orders: per-series order-up-to quantile of each arm's
            # own selection residuals at level q
            q_cost = np.quantile(sel_cost, q, axis=(0, 2))
            q_mae = np.quantile(sel_mae, q, axis=(0, 2))
            orders = {
                "routed_cost": np.maximum(pred_cost[idx] + q_cost[ser[idx]], 0.0),
                "routed": np.maximum(pred_mae[idx] + q_mae[ser[idx]], 0.0),
            }
            y_cls = y[idx]
            cost_c = NEWSVENDOR_HOLDING_COST * np.maximum(
                orders["routed_cost"] - y_cls, 0.0
            ) + NEWSVENDOR_STOCKOUT_COST * np.maximum(y_cls - orders["routed_cost"], 0.0)
            cost_m = NEWSVENDOR_HOLDING_COST * np.maximum(
                orders["routed"] - y_cls, 0.0
            ) + NEWSVENDOR_STOCKOUT_COST * np.maximum(y_cls - orders["routed"], 0.0)
            denom = float(y_cls.sum())
            per_q[f"q_{q:.2f}"] = {
                "routed_cost_per_unit_demand": float(cost_c.sum() / denom)
                if denom > 0
                else float("nan"),
                "routed_per_unit_demand": float(cost_m.sum() / denom)
                if denom > 0
                else float("nan"),
                "routed_cost_minus_routed": _paired_bootstrap_cost(
                    cost_c, cost_m, y_cls, ser[idx], config.bootstrap_reps, config.seed + 9721
                ),
            }
        counts = Counter(str(method_of_cost[i]) for i in np.flatnonzero(class_of_series == cls))
        per_class[cls] = {
            "mae": {
                "routed_cost": float(np.abs(pred_cost[idx] - y[idx]).mean()),
                "routed": float(np.abs(pred_mae[idx] - y[idx]).mean()),
                "routed_cost_minus_routed": mae_cls,
            },
            "newsvendor_per_unit_demand": per_q,
            "method_choices": dict(sorted(counts.items())),
        }
    counts_all = Counter(str(m) for m in method_of_cost)
    return {
        "simulation": True,
        "service_level": COST_ROUTING_LEVEL,
        "label": "cost-aware routing — per-series pick minimises summed newsvendor "
        "cost on the selection origins (documented cost assumptions, no savings claims)",
        "cost_assumptions": {
            "holding_cost_per_unit_ordered_unsold_per_day": NEWSVENDOR_HOLDING_COST,
            "stockout_cost_per_unit_short_per_day": NEWSVENDOR_STOCKOUT_COST,
            "order_rule": "order = max(pred + q_level(residuals on selection origins), 0) "
            "per series and routing arm",
        },
        "selection_cost_at_routing_level": selection_cost,
        "method_choices": {sid: str(method_of_cost[i]) for i, sid in enumerate(series_ids)},
        "method_choice_counts": dict(sorted(counts_all.items())),
        "overall_mae_test": {
            "routed_cost": float(np.abs(pred_cost - y).mean()),
            "routed": float(np.abs(pred_mae - y).mean()),
            "routed_cost_minus_routed": overall,
        },
        "per_class": per_class,
    }


# ---------------------------------------------------------------------------
# Convex ensemble (wave 21): per-series weight between the routed pick and the
# best ML candidate, chosen on the SELECTION origins only (no refits)
# ---------------------------------------------------------------------------


def ensemble_weights(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    n_series: int,
) -> dict[str, Any]:
    """Per-series convex blend of the routed pick and the best ML candidate.

    The best ML candidate is per series (lowest summed |error| over the
    selection origins among :data:`ML_SPARSE` — every series is eligible for
    the whole ML pool; class eligibility was the router's job). The weight
    w in {0, 0.1, ..., 1} (prediction = ``w · routed + (1 - w) · best_ml``)
    minimises each series' summed |error| over the selection cells — a pure
    post-processing of stored predictions, no refits. Reads no test-origin
    actual (property-tested alongside the router).
    """
    n_h = len(horizons)
    ml_err = {c: np.zeros(n_series) for c in ML_SPARSE}
    routed_err = np.zeros(n_series)
    R = np.zeros((n_series, n_h))
    M_stack = np.zeros((n_series, n_h, len(ML_SPARSE)))  # summed ML candidate preds
    Y = np.zeros((n_series, n_h))
    for o in selection:
        sc = by_origin[o]
        y = np.column_stack([units[o + h] for h in horizons])
        routed = np.column_stack([_routed_pred(sc, j, sparse, method_of) for j in range(n_h)])
        routed_err += np.abs(y - routed).sum(axis=1)
        for k, c in enumerate(ML_SPARSE):
            ml_err[c] += np.abs(y - sc.preds[c]).sum(axis=1)
            M_stack[:, :, k] += sc.preds[c]
        R += routed
        Y += y
    # best-ML pick from the COMPLETE selection errors, then blend per series
    ml_idx = np.argmin(np.stack([ml_err[c] for c in ML_SPARSE], axis=1), axis=1)
    ml_choice = np.array(ML_SPARSE, dtype=object)[ml_idx]
    M = np.take_along_axis(M_stack, ml_idx[:, None, None], axis=2)[:, :, 0]
    grid = np.round(np.linspace(0.0, 1.0, 11), 1)
    # errs[i, g] = summed |error| of series i under weight grid[g]
    errs = np.stack([np.abs(w * R + (1.0 - w) * M - Y).sum(axis=1) for w in grid], axis=1)
    w_pos = np.argmin(errs, axis=1)
    weights = grid[w_pos]
    n_cells = n_series * n_h * len(selection)
    from collections import Counter

    return {
        "weights": weights,
        "ml_choice": ml_choice,
        "grid": [float(w) for w in grid],
        "selection_mae": {
            "routed": float(routed_err.sum() / n_cells),
            "best_ml": float(
                np.stack([ml_err[c] for c in ML_SPARSE], axis=1).min(axis=1).sum() / n_cells
            ),
            "ensemble": float(errs[np.arange(n_series), w_pos].sum() / n_cells),
        },
        "weight_counts": {str(w): int(c) for w, c in sorted(Counter(weights).items())},
        "ml_choice_counts": {
            str(m): int(c) for m, c in sorted(Counter(str(m) for m in ml_choice).items())
        },
        "definition": "per series: pred = w * routed + (1 - w) * best_ml with best_ml = the "
        "ML_SPARSE candidate of lowest summed |error| on the selection origins; w in "
        "{0, 0.1, ..., 1} minimises the same selection loss — no refits, test origins "
        "never read",
    }


def _ensemble_pred(
    sc: OriginScore, routed_col: np.ndarray, weights: np.ndarray, ml_idx: np.ndarray, j: int
) -> np.ndarray:
    """The convex-ensemble point forecast for one (origin, horizon j) column:
    blend of the routed pipeline's per-series pick with that series' best ML
    candidate — ``w x routed + (1 - w) x best_ml`` (see :func:`ensemble_weights`)."""
    ml_stack = np.stack([sc.preds[c][:, j] for c in ML_SPARSE], axis=1)  # (n_s, n_c)
    best_ml = np.take_along_axis(ml_stack, ml_idx[:, None], axis=1)[:, 0]
    return np.asarray(weights * routed_col + (1.0 - weights) * best_ml, dtype=float)


def _routed_pred(sc: OriginScore, j: int, sparse: np.ndarray, method_of: np.ndarray) -> np.ndarray:
    del sparse  # eligibility is encoded in method_of by _route
    out = sc.preds["direct_hgb"][:, j].copy()
    for name in (*STATISTICAL_METHODS, *ML_SPARSE):
        mask = method_of == name
        out[mask] = sc.preds[name][mask, j]
    return out
