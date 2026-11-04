"""The long test-origin cell table and the ``_multistep`` JSON block assembly.

``_test_cells`` flattens (series x test origin x horizon) into column arrays
(one row per cell); the metric builders (per-horizon, bands, bootstrap suite,
growth curves, candidate comparison, rmae/rmsse) compute the sub-blocks;
``_assemble_block`` / ``_metadata_block`` shape the metrics.json and
evaluation_metadata.json payloads.
"""

import math
from typing import Any

import numpy as np

from demand_forecasting.config import ForecastConfig
from demand_forecasting.intermittent import ADI_THRESHOLD, CV2_THRESHOLD, STATISTICAL_METHODS
from demand_forecasting.multistep_constants import (
    CANDIDATES,
    CHAMPION,
    COMPARISON_CANDIDATES,
    FLOOR,
    LADDER_LEVELS,
    ML_SPARSE,
    NAIVE,
    PROTOCOL,
    QUANTILES_MS,
)
from demand_forecasting.multistep_features import ORIGIN_SPACING_DAYS
from demand_forecasting.multistep_metrics import (
    _paired_bootstrap_mae,
    _rmae_cells,
    _rmsse_cells,
    _scales,
    pinball_loss,
    rmsse_pooled,
)
from demand_forecasting.multistep_models import OriginScore
from demand_forecasting.multistep_routing import _ensemble_pred, _routed_pred
from demand_forecasting.probabilistic import (
    CALIBRATION_TOL,
    TARGET_COVERAGE,
    calibration_verdict,
)

# ---------------------------------------------------------------------------
# Long table over test origins
# ---------------------------------------------------------------------------


def _test_cells(
    by_origin: dict[int, OriginScore],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    series_ids: list[str],
    ens_weights: np.ndarray | None = None,
    ens_ml_idx: np.ndarray | None = None,
) -> dict[str, Any]:
    """Flatten (series x test origin x horizon) into column arrays."""
    n_cells = units.shape[1] * len(test) * len(horizons)
    # country block per series (store = country in the UCI panel) for the
    # wave-22 hierarchy anchoring: total -> country -> (country, product)
    country_of = np.array([sid.split("|")[0] for sid in series_ids], dtype=object)
    cells: dict[str, Any] = {
        "series": np.empty(n_cells, dtype=int),
        "origin": np.empty(n_cells, dtype=int),
        "h": np.empty(n_cells, dtype=int),
        "y": np.empty(n_cells),
        "sparse": np.empty(n_cells, dtype=bool),
        "scale": np.empty(n_cells),
        "scale2": np.empty(n_cells),
        "volume": np.empty(n_cells),
        "pred": {name: np.empty(n_cells) for name in CANDIDATES},
        "p50": np.empty(n_cells),
        "p10": np.empty(n_cells),
        "p90": np.empty(n_cells),
    }
    r = 0
    for o in test:
        sc = by_origin[o]
        sc_mase, sc_scale2, sc_vol = _scales(units, o)
        for j, h in enumerate(horizons):
            n = units.shape[1]
            sl = slice(r, r + n)
            cells["series"][sl] = np.arange(n)
            cells["origin"][sl] = o
            cells["h"][sl] = h
            cells["y"][sl] = units[o + h]
            cells["sparse"][sl] = sparse
            cells["scale"][sl] = sc_mase
            cells["scale2"][sl] = sc_scale2
            cells["volume"][sl] = sc_vol
            cells["p50"][sl] = sc.quantiles[0.5][:, j]
            cells["p10"][sl] = sc.quantiles[0.1][:, j]
            cells["p90"][sl] = sc.quantiles[0.9][:, j]
            for name in (
                "direct_hgb",
                "seasonal_naive",
                "zero",
                "croston",
                "sba",
                "tsb",
                "ma_28",
                "adida_sba",
                "adida_tsb",
                "hgb_tweedie",
                "hurdle_hgb",
                "lgbm_tweedie",
                "lgbm_poisson",
                "hurdle_lgbm",
                "peak_weighted_hgb",
            ):
                cells["pred"][name][sl] = sc.preds[name][:, j]
            routed = _routed_pred(sc, j, sparse, method_of)
            cells["pred"]["routed"][sl] = routed
            cells["pred"]["routed_reconciled"][sl] = _reconciled_pred(
                units, sc, j, sparse, method_of, country_of, horizons
            )
            if ens_weights is not None and ens_ml_idx is not None:
                cells["pred"]["ensemble_convex"][sl] = _ensemble_pred(
                    sc, routed, ens_weights, ens_ml_idx, j
                )
            r += n
    return cells


def _reconciled_pred(
    units: np.ndarray,
    sc: OriginScore,
    j: int,
    sparse: np.ndarray,
    method_of: np.ndarray,
    country_of: np.ndarray,
    horizons: list[int],
) -> np.ndarray:
    """Hierarchy-anchored post-processing of the routed forecast (wave 22).

    For horizon index ``j`` (true horizon h), each country block is anchored
    to the seasonal-naive forecast of the country's AGGREGATED demand on the
    target day — a genuinely independent, denser signal than any member
    series. The discrepancy (anchor - sum of member routed forecasts) is
    allocated to member series proportionally to their routed forecast;
    members with zero forecast get nothing. If every member forecast in the
    block is zero, the discrepancy is allocated proportionally to the member
    training-window means (up to the origin); if those are all zero too, the
    block is left unadjusted. Pure numpy, deterministic.
    """
    origin = sc.origin
    h = horizons[j]
    ref = origin + h - 7 * math.ceil(h / 7)  # seasonal-naive reference day
    routed = _routed_pred(sc, j, sparse, method_of)
    countries = np.unique(country_of)
    anchor = np.zeros(countries.shape[0])
    for c_i, c in enumerate(countries):
        members = country_of == c
        anchor[c_i] = units[ref][members].sum()
    train_mean = units[: origin + 1].mean(axis=0)
    out = routed.copy()
    for c_i, c in enumerate(countries):
        members = np.flatnonzero(country_of == c)
        block_sum = float(routed[members].sum())
        discrepancy = anchor[c_i] - block_sum
        if discrepancy == 0.0:
            continue
        if block_sum > 0:
            weights = routed[members] / block_sum
        else:
            mean_sum = float(train_mean[members].sum())
            if mean_sum <= 0:
                continue  # nothing to allocate to: no adjustment
            weights = train_mean[members] / mean_sum
        out[members] = routed[members] + discrepancy * weights
    return out


# ---------------------------------------------------------------------------
# Per-horizon metric suite
# ---------------------------------------------------------------------------


def _metric_dict(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> dict[str, float]:
    """Pooled MAE/RMSE/MASE/bias/WAPE for one candidate over the masked cells."""
    y = cells["y"][mask]
    err = cells["pred"][pred_key][mask] - y
    abs_err = np.abs(err)
    scale_mask = cells["scale"][mask] > 0
    mase = (
        float(abs_err[scale_mask].sum() / cells["scale"][mask][scale_mask].sum())
        if scale_mask.any()
        else float("nan")
    )
    abs_y = float(np.abs(y).sum())
    return {
        "n": int(mask.sum()),
        "mae": float(abs_err.mean()),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mase": mase,
        "bias": float(err.mean()),
        "wape": float(abs_err.sum() / abs_y) if abs_y > 0 else float("nan"),
    }


def _per_horizon_metrics(cells: dict[str, Any], horizons: list[int]) -> dict[int, dict[str, Any]]:
    """Pooled MAE/RMSE/MASE/bias/WAPE/RMSSE per TRUE horizon (test origins).

    Errors now genuinely grow with h — the growth curve is the point.
    MASE divides the pooled |err| by the pooled per-series seasonal scale
    (zero-scale rows excluded); RMSSE is M5-style per series, reported pooled
    and volume-weighted. Champion and floor metrics are both carried.
    """
    out: dict[int, dict[str, Any]] = {}
    for h in horizons:
        mask = cells["h"] == h
        entry: dict[str, Any] = {
            "champion": _metric_dict(cells, mask, CHAMPION),
            "floor": _metric_dict(cells, mask, FLOOR),
        }
        err = cells["pred"][CHAMPION][mask] - cells["y"][mask]
        rmsse, wrmsse = rmsse_pooled(
            err, cells["scale2"][mask], cells["volume"][mask], cells["series"][mask]
        )
        entry["champion"]["rmsse"] = rmsse
        entry["champion"]["wrmsse"] = wrmsse
        out[h] = entry
    return out


# ---------------------------------------------------------------------------
# Bands: split-conformal per h (learner) + sparse P(sale)/ladder bands
# ---------------------------------------------------------------------------


def _bands(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    cells: dict[str, Any],
) -> dict[str, Any]:
    """Per-horizon bands on the test origins.

    Learner rows (smooth/erratic): ±q80 split-conformal width per h,
    calibrated on the selection origins' p50 residuals, zero-clipped and
    sorted. Sparse rows (routed): band [0, q90 of the training history] plus
    P(any sale) and a quantile ladder — it cannot collapse to zero width.
    Returns the per-h coverage/width table (metrics) plus the probabilistic.json
    block (keyed "json").
    """
    # conformal widths per h from selection-origin p50 residuals (learner rows)
    widths: dict[int, float] = {}
    for h in horizons:
        res: list[np.ndarray] = []
        for o in selection:
            sc = by_origin[o]
            j = horizons.index(h)
            res.append(units[o + h][~sparse] - sc.quantiles[0.5][~sparse, j])
        widths[h] = float(np.quantile(np.abs(np.concatenate(res)), TARGET_COVERAGE))

    units.shape[1]
    per_h: dict[int, dict[str, Any]] = {}
    sparse_band: dict[str, Any] = {}
    for h in horizons:
        mask = cells["h"] == h
        y = cells["y"][mask]
        lo = np.empty(mask.sum())
        hi = np.empty(mask.sum())
        # learner rows: p50 ± width, zero-clipped (sorting is then automatic)
        p50 = cells["p50"][mask]
        w = widths[h]
        lo[:] = np.clip(p50 - w, 0.0, None)
        hi[:] = p50 + w
        # sparse rows: [0, q90 of the training history up to the origin]
        sparse_rows = np.flatnonzero(cells["sparse"][mask])
        for r in sparse_rows:
            i = int(cells["series"][mask][r])
            o = int(cells["origin"][mask][r])
            hist = units[: o + 1, i]
            lo[r] = 0.0
            hi[r] = float(np.quantile(hist, TARGET_COVERAGE))
        covered = (y >= lo) & (y <= hi)
        per_h[h] = {
            "coverage": float(covered.mean()),
            "avg_width": float((hi - lo).mean()),
            "calibration_verdict": calibration_verdict(float(covered.mean()), TARGET_COVERAGE),
            "learner_coverage": float(covered[~cells["sparse"][mask]].mean())
            if (~cells["sparse"][mask]).any()
            else float("nan"),
            "sparse_coverage": float(covered[cells["sparse"][mask]].mean())
            if cells["sparse"][mask].any()
            else float("nan"),
        }

    # pinball loss of the learner quantiles per h (on learner rows)
    pinball: dict[int, dict[str, float]] = {}
    for h in horizons:
        mask = (cells["h"] == h) & (~cells["sparse"])
        pinball[h] = {
            f"pinball_p{int(q * 100)}": pinball_loss(
                cells["y"][mask], cells[f"p{int(q * 100)}"][mask], q
            )
            for q in QUANTILES_MS
        }

    # sparse band summary from the LAST test origin (dataset-level flavour)
    last_o = max(test)
    sparse_band = {
        "definition": (
            "P(any sale) = share of non-zero demand days in the training history "
            "up to the origin; quantile ladder over the same history"
        ),
        "ladder_levels": list(LADDER_LEVELS),
        "series": {
            str(i): {
                "p_sale": float(np.mean(units[: last_o + 1, i] > 0)),
                "ladder": [
                    float(np.quantile(units[: last_o + 1, i], lvl)) for lvl in LADDER_LEVELS
                ],
            }
            for i in np.flatnonzero(sparse)
        },
    }

    # bands for the peak-capable candidates: conformal width per h from the
    # selection-origin residuals around the candidate's own point forecast
    # (zero-clipped and sorted — clipping floors at 0, so sorting is
    # automatic); sparse rows honestly keep the P(sale)+ladder band as today.
    candidate_bands: dict[str, Any] = {}
    for cand in ML_SPARSE:
        cand_widths: dict[int, float] = {}
        for h in horizons:
            j = horizons.index(h)
            res_c = np.concatenate(
                [units[o + h] - by_origin[o].preds[cand][:, j] for o in selection]
            )
            cand_widths[h] = float(np.quantile(np.abs(res_c), TARGET_COVERAGE))
        cand_per_h: dict[int, dict[str, Any]] = {}
        for h in horizons:
            mask = cells["h"] == h
            y = cells["y"][mask]
            lo_c = np.clip(cells["pred"][cand][mask] - cand_widths[h], 0.0, None)
            hi_c = cells["pred"][cand][mask] + cand_widths[h]
            sparse_rows = np.flatnonzero(cells["sparse"][mask])
            for r in sparse_rows:
                i = int(cells["series"][mask][r])
                o = int(cells["origin"][mask][r])
                lo_c[r] = 0.0
                hi_c[r] = float(np.quantile(units[: o + 1, i], TARGET_COVERAGE))
            covered_c = (y >= lo_c) & (y <= hi_c)
            cand_per_h[h] = {
                "coverage": float(covered_c.mean()),
                "avg_width": float((hi_c - lo_c).mean()),
                "calibration_verdict": calibration_verdict(
                    float(covered_c.mean()), TARGET_COVERAGE
                ),
            }
        candidate_bands[cand] = {
            "band_type": "point ± q80 split-conformal width per horizon, calibrated on the "
            "selection origins, zero-clipped and sorted; sparse rows carry the P(sale)+"
            "quantile-ladder history band instead",
            "conformal_widths_by_h": {str(h): cand_widths[h] for h in horizons},
            "per_horizon": {str(h): cand_per_h[h] for h in horizons},
            "pooled_coverage": float(np.mean([cand_per_h[h]["coverage"] for h in horizons])),
            "pooled_verdict": calibration_verdict(
                float(np.mean([cand_per_h[h]["coverage"] for h in horizons])), TARGET_COVERAGE
            ),
        }

    pooled_cov = float(np.mean([per_h[h]["coverage"] for h in horizons]))
    block = {
        "protocol": PROTOCOL,
        "target_coverage": TARGET_COVERAGE,
        "calibration_tolerance": CALIBRATION_TOL,
        "band_types": {
            "learner": "p50 ± q80 split-conformal width per horizon, calibrated on the "
            "selection origins, zero-clipped and sorted",
            "sparse": "P(any sale) + quantile ladder of the training history (no collapsing band)",
            "candidate": "peak-capable candidates (hgb_tweedie / hurdle_hgb): point ± q80 "
            "split-conformal width per horizon around the candidate's own point forecast, "
            "zero-clipped and sorted; sparse rows keep the P(sale)+ladder band",
        },
        "conformal_widths_by_h": {str(h): widths[h] for h in horizons},
        "per_horizon": {str(h): {**per_h[h], **pinball[h]} for h in horizons},
        "candidate_bands": candidate_bands,
        "pooled_coverage": pooled_cov,
        "pooled_verdict": calibration_verdict(pooled_cov, TARGET_COVERAGE),
        "sparse_band": sparse_band,
        "verdict_rule": "|coverage - target| <= 0.05 -> calibrated; above target -> "
        "conservative; below -> optimistic (per horizon and pooled)",
    }
    return {"per_h": per_h, "widths": widths, "json": block}


# ---------------------------------------------------------------------------
# Paired bootstrap suite
# ---------------------------------------------------------------------------


def _bootstrap_suite(
    cells: dict[str, Any], horizons: list[int], config: ForecastConfig
) -> dict[str, Any]:
    """95% cluster-bootstrap CIs on every headline comparison.

    Unit = (series x scored test origins): series are resampled with
    replacement, one shared draw per replication so differences stay paired.
    """
    seed = config.seed + 2002  # distinct stream from every other consumer
    classes = [str(c) for c in np.unique(cells["class"])]

    def _pair(mask: np.ndarray, a: str, b: str) -> dict[str, Any]:
        return _paired_bootstrap_mae(
            cells["pred"][a][mask] - cells["y"][mask],
            cells["pred"][b][mask] - cells["y"][mask],
            cells["series"][mask],
            config.bootstrap_reps,
            seed,
        )

    per_class: dict[str, Any] = {}
    for cls in classes:
        cls_mask = cells["class"] == cls
        entry: dict[str, Any] = {}
        for h in (7, 14):
            if h not in horizons:
                continue
            mask = cls_mask & (cells["h"] == h)
            if not mask.any():
                continue
            h_entry: dict[str, Any] = {
                "champion_mae": float(
                    np.abs(cells["pred"][CHAMPION][mask] - cells["y"][mask]).mean()
                ),
                "floor_mae": float(np.abs(cells["pred"][FLOOR][mask] - cells["y"][mask]).mean()),
                "champion_vs_floor": _pair(mask, CHAMPION, FLOOR),
                "champion_vs_naive_zero": _pair(mask, CHAMPION, NAIVE),
            }
            # peak-capable candidates vs the routed pipeline and the zero floor
            for cand in COMPARISON_CANDIDATES:
                h_entry[f"{cand}_mae"] = float(
                    np.abs(cells["pred"][cand][mask] - cells["y"][mask]).mean()
                )
                h_entry[f"{cand}_vs_routed"] = _pair(mask, cand, CHAMPION)
                h_entry[f"{cand}_vs_zero"] = _pair(mask, cand, NAIVE)
            entry[f"h{h}"] = h_entry
        # routing before/after: all-HGB (unrouted) vs routed champion, all h
        entry["routing"] = _pair(cls_mask, "direct_hgb", CHAMPION)
        entry["n_series"] = len(np.unique(cells["series"][cls_mask]))
        per_class[cls] = entry

    # model ranks pooled over test origins and all horizons (with rank gaps)
    overall_mae = {
        name: float(np.abs(cells["pred"][name] - cells["y"]).mean()) for name in CANDIDATES
    }
    ranked = sorted(CANDIDATES, key=lambda n: overall_mae[n])
    rank_gaps: list[dict[str, Any]] = []
    for rank, name in enumerate(ranked[:5], start=1):
        gap: dict[str, Any] = {"rank": rank, "model": name, "mae": overall_mae[name]}
        if rank < len(ranked):
            nxt = ranked[rank]
            gap["gap_to_next"] = {
                "model": nxt,
                **_paired_bootstrap_mae(
                    cells["pred"][name] - cells["y"],
                    cells["pred"][nxt] - cells["y"],
                    cells["series"],
                    config.bootstrap_reps,
                    seed,
                ),
            }
        rank_gaps.append(gap)

    return {
        "method": "paired cluster bootstrap (series resampled with replacement, one shared "
        "draw per replication), percentile 95% CI over series x scored test origins",
        "unit": "series cluster x scored test origins",
        "n_boot": config.bootstrap_reps,
        "seed": seed,
        "per_class": per_class,
        "rank_gaps": rank_gaps,
    }


# ---------------------------------------------------------------------------
# Horizon growth curves
# ---------------------------------------------------------------------------


def _growth_curves(cells: dict[str, Any], horizons: list[int]) -> dict[str, Any]:
    """Pooled MAE by TRUE horizon for the champion, the floor and zero."""
    curves: dict[str, Any] = {"pooled": {}, "per_class": {}}
    for name in (CHAMPION, FLOOR, NAIVE):
        curves["pooled"][name] = {
            str(h): float(
                np.abs(cells["pred"][name][cells["h"] == h] - cells["y"][cells["h"] == h]).mean()
            )
            for h in horizons
        }
    for cls in np.unique(cells["class"]):
        cls_mask = cells["class"] == cls
        curves["per_class"][str(cls)] = {
            name: {
                str(h): float(
                    np.abs(
                        cells["pred"][name][cls_mask & (cells["h"] == h)]
                        - cells["y"][cls_mask & (cells["h"] == h)]
                    ).mean()
                )
                for h in horizons
            }
            for name in (CHAMPION, FLOOR)
        }
    return curves


# ---------------------------------------------------------------------------
# Candidate comparison (pooled over horizons, per class)
# ---------------------------------------------------------------------------


def _candidate_comparison(cells: dict[str, Any], config: ForecastConfig) -> dict[str, Any]:
    """Pooled-over-h MAE of the peak-capable candidates vs the routed/zero
    baselines, per class, with paired cluster-bootstrap CIs on every gap."""
    seed = config.seed + 6402  # distinct bootstrap stream
    classes = [str(c) for c in np.unique(cells["class"])]
    per_class: dict[str, Any] = {}
    for cls in classes:
        mask = cells["class"] == cls
        entry: dict[str, Any] = {
            "routed_mae": float(np.abs(cells["pred"][CHAMPION][mask] - cells["y"][mask]).mean()),
            "zero_mae": float(np.abs(cells["pred"][NAIVE][mask] - cells["y"][mask]).mean()),
        }
        for cand in COMPARISON_CANDIDATES:
            item: dict[str, Any] = {
                "mae": float(np.abs(cells["pred"][cand][mask] - cells["y"][mask]).mean())
            }
            for base_name, base in (("routed", CHAMPION), ("zero", NAIVE)):
                item[f"vs_{base_name}"] = _paired_bootstrap_mae(
                    cells["pred"][cand][mask] - cells["y"][mask],
                    cells["pred"][base][mask] - cells["y"][mask],
                    cells["series"][mask],
                    config.bootstrap_reps,
                    seed,
                )
            entry[cand] = item
        per_class[cls] = entry
    return {
        "method": "pooled MAE over series x scored test origins x all horizons; gaps carry "
        "a 95% paired cluster bootstrap CI over series (negative diff = candidate better)",
        "candidates": list(COMPARISON_CANDIDATES),
        "n_boot": config.bootstrap_reps,
        "seed": seed,
        "per_class": per_class,
    }


# ---------------------------------------------------------------------------
# Wave-22 relative-error blocks: rmae + per-candidate rmsse (per class/pooled)
# ---------------------------------------------------------------------------


def _rmae_block(cells: dict[str, Any]) -> dict[str, Any]:
    """Relative MAE (candidate pooled MAE / seasonal_naive floor pooled MAE)
    for every candidate, pooled and per demand class. The floor itself sits at
    1.0 by construction; this is the headline ratio the claim quotes."""
    full = np.ones(cells["y"].shape[0], dtype=bool)
    classes = [str(c) for c in np.unique(cells["class"])]
    return {
        "definition": "rmae = candidate pooled MAE / seasonal_naive floor pooled MAE over "
        "the same scored cells; < 1 = beats the floor (the floor's rmae is 1.0 "
        "by construction)",
        "pooled": {name: _rmae_cells(cells, full, name) for name in CANDIDATES},
        "per_class": {
            cls: {name: _rmae_cells(cells, cells["class"] == cls, name) for name in CANDIDATES}
            for cls in classes
        },
    }


def _rmsse_block(cells: dict[str, Any]) -> dict[str, Any]:
    """Per-candidate RMSSE (M5 convention, see :func:`_rmsse_cells`), pooled
    and per demand class, with the volume-weighted variant alongside."""

    def _entry(mask: np.ndarray, name: str) -> dict[str, float]:
        r, wr = _rmsse_cells(cells, mask, name)
        return {"rmsse": r, "wrmsse": wr}

    full = np.ones(cells["y"].shape[0], dtype=bool)
    classes = [str(c) for c in np.unique(cells["class"])]
    return {
        "definition": "M5-style RMSSE per (series x scored origin) unit: numerator = MSE of "
        "the candidate over the unit's scored horizon days, denominator = in-sample MSE of "
        "the one-step seasonal-naive-7 over the unit's training window; averaged over units "
        "(zero-scale units excluded); wrmsse weights by training-window volume",
        "pooled": {name: _entry(full, name) for name in CANDIDATES},
        "per_class": {
            cls: {name: _entry(cells["class"] == cls, name) for name in CANDIDATES}
            for cls in classes
        },
    }


# ---------------------------------------------------------------------------
# Block assembly
# ---------------------------------------------------------------------------


def _assemble_block(
    dates: np.ndarray,
    origins: list[int],
    selection: list[int],
    test: list[int],
    horizons: list[int],
    classes: dict[str, dict[str, Any]],
    sparse: np.ndarray,
    method_of: np.ndarray,
    per_horizon: dict[int, dict[str, Any]],
    bands: dict[str, Any],
    bootstrap: dict[str, Any],
    growth: dict[str, Any],
    decision: dict[str, Any],
    cells: dict[str, Any],
    series_ids: list[str],
    config: ForecastConfig,
    correction: dict[str, Any],
    peak: dict[str, Any],
    win_rates: dict[str, Any],
    pw_choice: dict[str, Any],
    ens: dict[str, Any],
    cost_aware: dict[str, Any],
) -> dict[str, Any]:
    """The ``_multistep`` block of metrics.json (multi-step headline)."""
    del bands  # band numbers live in probabilistic.json (merged separately)
    counts = {
        cls: int(sum(1 for s in series_ids if classes[s]["class"] == cls))
        for cls in ("smooth", "erratic", "intermittent", "lumpy")
    }
    headline: dict[str, Any] = {}
    for cls, entry in bootstrap["per_class"].items():
        headline[cls] = {key: value for key, value in entry.items() if key.startswith("h")}
        headline[cls]["n_series"] = entry["n_series"]
    routing_choices = {sid: str(method_of[i]) for i, sid in enumerate(series_ids)}
    overall = {name: float(np.abs(cells["pred"][name] - cells["y"]).mean()) for name in CANDIDATES}
    rmae = _rmae_block(cells)
    champ_mae = overall[CHAMPION]
    headline_claim = (
        f"champion '{CHAMPION}' pooled test MAE {champ_mae:.2f} vs floor '{FLOOR}' "
        f"{overall[FLOOR]:.2f} — rmae {rmae['pooled'][CHAMPION]:.3f} "
        "(relative MAE vs the seasonal-naive floor; < 1 beats the floor)"
    )
    return {
        "protocol": PROTOCOL,
        "track_note": (
            "PRIMARY multi-step headline. The per-model blocks above are the retained "
            "frozen nowcast (one-day-ahead) track, rolling_origin_holdout_v1 — valid but "
            "never mixed into the multi-step leaderboard. Each multi-step row is a TRUE "
            "horizon-h forecast issued at the origin (no actual within h days of the "
            "target is referenced)."
        ),
        "horizons": horizons,
        "window_days": config.multistep_window_days,
        "candidates": list(CANDIDATES),
        "champion": CHAMPION,
        "champion_definition": "per-series routing: sparse (ADI>=1.32) series -> best candidate "
        "among the statistical methods (zero/seasonal_naive/Croston/SBA/TSB + the wave-22 "
        "ma_28/ADIDA pair) + the six peak-capable ML candidates on the selection origins; "
        "smooth/erratic -> best among direct_hgb + the same ML pool",
        "floor": FLOOR,
        "naive": NAIVE,
        "peak_capable_candidates": {
            "hgb_tweedie": "HGBRegressor with the compound-Poisson tweedie deviance "
            "(variance power 1.5); lr/depth/leaves tuned on the selection origins via a "
            "seeded capped Optuna study (hpo.tune_multistep_tweedie)",
            "hurdle_hgb": "per-h two-stage HGB: log-loss classifier for P(sale) + HGB on "
            "log1p(non-zero sizes); point = p_hat x (exp(y_reg) - 1), zero-corrected on the "
            "selection origins (identity / scalar / isotonic — whichever wins there)",
            "lgbm_tweedie": "global LightGBM with the tweedie objective (variance power "
            "1.5), series identity as hi/lo categoricals; lr/leaves/min_child_samples tuned "
            "on the selection origins via a seeded capped Optuna study (hpo.tune_multistep_lgbm)",
            "lgbm_poisson": "global LightGBM with the poisson count objective — same "
            "features, same tuning contract as lgbm_tweedie",
            "hurdle_lgbm": "the two-stage hurdle on LightGBM halves (classifier x "
            "log1p-size regressor), same raw point math and the same selection-origin "
            "zero-correction as hurdle_hgb",
            "peak_weighted_hgb": "the HGB hurdle pair fit with sample weights 2-3 on each "
            "series' top-decile demand days; the weight is chosen on the selection origins, "
            "then the same zero-correction applies",
            "ensemble_convex": "per-series convex blend w x routed + (1 - w) x best_ml "
            "(w in {0, 0.1, ..., 1}, best_ml = the per-series best ML candidate, both "
            "chosen on the selection origins; no refits)",
        },
        "post_processing_candidates": {
            "routed_reconciled": "hierarchy anchoring of the routed forecast (comparison-"
            "only, never in the routing pool): per country block the anchor is the "
            "seasonal-naive forecast of the country's aggregated demand on the target day; "
            "the discrepancy is allocated to member series proportionally to their routed "
            "forecast (fallback: training-window means; then no adjustment)"
        },
        "origins": {
            "n_origins": len(origins),
            "dates": [str(dates[o])[:10] for o in origins],
            "selection_dates": [str(dates[o])[:10] for o in selection],
            "test_dates": [str(dates[o])[:10] for o in test],
            "spacing_days": ORIGIN_SPACING_DAYS,
            "min_train_dates": config.min_train_size,
            "gap_days": 0,
            "cap_note": (
                f"weekly origins, capped at {config.multistep_n_origins} by dropping the "
                "oldest (exact weekly cadence kept) for runtime; the window starts the day "
                "AFTER the origin (no embargo gap)"
            ),
        },
        "demand_classes": {
            "method": "Syntetos-Boylan quadrants on ADI and CV^2 over the full panel",
            "thresholds": {"adi": ADI_THRESHOLD, "cv2": CV2_THRESHOLD},
            "counts": counts,
            "n_series": len(series_ids),
            "sparse_share": float(sparse.mean()),
            "series": {sid: classes[sid]["class"] for sid in series_ids},
        },
        "routing": {
            "rule": "per-series routing on the selection origins ONLY: sparse (ADI >= 1.32) "
            "series choose among zero/seasonal_naive/Croston/SBA/TSB/ma_28/adida_sba/"
            "adida_tsb plus the six peak-capable ML candidates; smooth/erratic series "
            "choose among direct_hgb plus the same ML pool",
            "method_choices": routing_choices,
            "pool_sparse": list((*STATISTICAL_METHODS, *ML_SPARSE)),
            "pool_dense": list(("direct_hgb", *ML_SPARSE)),
            "hurdle_correction": correction,
            "peak_weight_choice": pw_choice,
            "ensemble": {
                k: v
                for k, v in ens.items()
                if k not in ("ml_choice", "weights")  # numpy arrays, not JSON-safe
            },
            "per_class": {cls: entry["routing"] for cls, entry in bootstrap["per_class"].items()},
            "cost_aware": cost_aware,
        },
        "headline_per_class": headline,
        "candidate_comparison": _candidate_comparison(cells, config),
        "peak_capture": peak,
        "win_rates": win_rates,
        "per_horizon": {str(h): per_horizon[h] for h in horizons},
        "horizon_growth": growth,
        "overall_mae_test": overall,
        "headline_claim": headline_claim,
        "rmae": rmae,
        "rmsse": _rmsse_block(cells),
        "bootstrap": {
            "method": bootstrap["method"],
            "unit": bootstrap["unit"],
            "n_boot": bootstrap["n_boot"],
            "seed": bootstrap["seed"],
            "rank_gaps": bootstrap["rank_gaps"],
        },
        "decision_metric": decision,
    }


def _metadata_block(block: dict[str, Any], config: ForecastConfig) -> dict[str, Any]:
    """The ``multi_horizon`` block of evaluation_metadata.json (protocol v2)."""
    origins = block["origins"]
    return {
        "protocol": PROTOCOL,
        "track": "multi_step (primary); the top-level rolling_origin_holdout_v1 keys "
        "describe the retained frozen nowcast track",
        "horizons": block["horizons"],
        "window_days": block["window_days"],
        "origins": origins,
        "holdout_designation": (
            f"last {config.multistep_test_origins} origins = test (scored once); the "
            "earlier origins select (routing + conformal calibration) only"
        ),
        "selection_rule": "per-series routing method = lowest summed |error| over the "
        "selection origins: sparse series among zero/seasonal_naive/Croston/SBA/TSB/"
        "ma_28/adida_sba/adida_tsb plus the six ML candidates (direct_hgb ineligible — "
        "the wave-19 sparse finding); smooth/erratic series among direct_hgb plus the "
        "same ML pool; the convex-ensemble weight and the peak-weighted hurdle's sample "
        "weight are chosen on the same selection origins; never reads test actuals "
        "(property-tested by shuffling the test origins' actuals)",
        "feature_semantics": "direct per-horizon models: calendar of the target date (incl. "
        "is_month_end / week_of_month, the wholesale trading-cycle hypothesis) + peak block "
        "at target-h (rolling mean/max over 7/14/28d windows ending at target-h, "
        "days-since-last-nonzero, 28d non-zero-day count, 28d peak ratio) + price block at "
        "target-h (price_asof, price_ratio_28d, days_since_price_change, price_drop — the "
        "B2B promo proxy; neutral constants when the panel has no price column) + rolling "
        "block at target-h (wave 22: rmean7/rmean14/rmean28, rstd14/rstd28 — rolling "
        "means/stds of demand over windows ending at target-h) + lags "
        "lag_h, lag_{h+7}, lag_{h+14} (every demand/price feature >= h days old relative "
        "to the target — no actual within h days of the target is referenced, taint-tested "
        "for units AND price); training rows use targets <= the origin only",
        "uncertainty": "per-horizon split-conformal (learner rows and the peak-capable "
        "candidates' own point forecasts) and P(sale)+quantile ladder (sparse rows), both "
        "calibrated on selection origins",
        "metric_definitions": {
            "mae": "mean |actual - forecast| over series x scored test origins at horizon h",
            "mase": "pooled |err| / pooled per-series in-sample seasonal-naive-7 scale "
            "(zero-scale rows excluded); 1.0 is the scale's in-sample error level, "
            "NOT the naive's own holdout error — the naive's MASE can differ from "
            "1.0 on a scored window",
            "rmae": "candidate pooled MAE / seasonal_naive floor pooled MAE over the same "
            "scored cells; < 1 = beats the floor (the floor sits at 1.0 by construction)",
            "rmsse": "M5-style per (series x scored origin) unit: sqrt(MSE(candidate) / "
            "in-sample MSE of the one-step seasonal-naive-7 on the unit's training window), "
            "averaged over units (zero-scale excluded)",
            "wrmsse": "volume-weighted RMSSE (weights = training-window demand)",
            "bias": "mean(forecast - actual) at horizon h",
            "wape": "sum|err| / sum|actual| at horizon h",
            "pinball_pXX": "mean pinball loss of the learner quantile at level XX",
            "coverage": "share of actuals inside the per-h band on the scored origins",
            "calibration_verdict": "|coverage - target| <= 0.05 -> calibrated; above -> "
            "conservative; below -> optimistic",
            "peak_mae": "per scored window (series x test origin), MAE on the window's "
            "top-decile-by-actual days of the scored h-lattice; pooled per class as the "
            "mean over windows",
            "peak_recall": "per scored window, the share of the window's top-5 actual days "
            "whose day ranks in the forecast's own top-5; pooled per class as the mean "
            "over windows",
            "win_rate": "per class and horizon: the share of series whose summed |error| "
            "over the scored test origins at that h is strictly below the seasonal_naive "
            "floor's; 95% CI = cluster bootstrap over series (one shared index draw per "
            "replication across candidates)",
            "newsvendor_cost": "decision layer (documented assumption, not a measured "
            "saving): order = the routed band's q-quantile (dense rows interpolate the "
            "committed p10/p50/p90 ladder; sparse rows read the training-history ladder; "
            "the floor reads the same quantile of the seasonal-naive empirical "
            "distribution = training demand on the target's weekday); cost = 1.0 x "
            "ordered-but-unsold + 3.0 x unmet per unit per day; reported per class as "
            "expected daily cost per unit-demand with a paired cluster-bootstrap CI",
        },
        "candidates": list(CANDIDATES),
    }
