"""Direct multi-horizon forecasting track — protocol ``direct_multihorizon_v1``.

The nowcast track (evaluate.py) answers "tomorrow, given today". This module
answers the question replenishment actually asks: **the next 14 days, issued
once per week**, with each horizon modelled directly:

- **Direct per-horizon models** — one model per horizon
  ``h ∈ config.multistep_horizons``. Features for horizon *h* are the calendar
  of the target date (known in advance) plus lags aged ≥ *h* days relative to
  the target: ``lag_h = units(target - h)``, ``lag_{h+7}``, ``lag_{h+14}``.
  Relative to the origin (issue date *t*, target *t+h*) these are
  ``units(t)``, ``units(t-7)``, ``units(t-14)`` — so **no actual within *h*
  days of the target is ever referenced**, by construction (leakage-proof
  tested with tainted panels). The learner is the champion-config HGB
  (``config.hgb_tuned``) with the series identity as a hi/lo pair of native
  categoricals (HGB caps categorical cardinality at 255; the exact pair
  (id // 64, id % 64) keeps both cardinalities small and memory flat — a
  dense one-hot over 1,600 series would not survive parallel origin fits).
- **Weekly rolling origins** — origin = last training date; the forecast
  window is the 14 days *starting the day after the origin* (no embargo gap —
  the 57-day hole of the nowcast layout is gone). Origins are 7 days apart,
  capped at ``config.multistep_n_origins`` by dropping the oldest (the exact
  weekly cadence is preserved; the cap is documented). The LAST
  ``config.multistep_test_origins`` origins are the test set — scored once,
  never read for selection; the earlier origins select (per-series routing
  method, conformal widths).
- **Routing** — series are routed per class on the selection origins only:
  sparse quadrants (ADI ≥ 1.32, see intermittent.py) choose among the
  statistical methods (zero / seasonal_naive / Croston / SBA / TSB + the
  wave-22 ma_28 / ADIDA pair) PLUS the wave-20 peak-capable ML models
  (hgb_tweedie / hurdle_hgb, below) — direct_hgb stays excluded there (the
  wave-19 finding: boosted trees overfit sparse series); smooth/erratic series
  choose among direct_hgb and the two ML candidates. Selection on train
  origins only is property-tested (shuffling the test origins' actuals leaves
  the routing unchanged).
- **Peak features** (wave 20) — the design adds a peak block computed at the
  reference day target-h (so >= h days older than the target, exactly like the)
  lags): rolling mean AND max over 7/14/28-day windows, days-since-last-
  non-zero, the 28d non-zero-day count and the 28d peak ratio. The flat
  intermittent estimators cannot see any of these.
- **Peak-capable candidates** (wave 20) — two ML entries join the sparse
  routing pool, both on the hi/lo series-identity categoricals:
  ``hgb_tweedie`` (HGB with the compound-Poisson tweedie deviance, variance
  power 1.5; lr/depth/leaves tuned on the selection origins by a seeded
  capped Optuna study, hpo.tune_multistep_tweedie) and ``hurdle_hgb`` (per-h
  two-stage HGB: log-loss classifier for P(sale) + HGB on log1p(non-zero
  sizes); point = p_hat x (exp(y_reg) - 1), zero-corrected on the selection origins -
  identity / scalar / isotonic, whichever wins there, tested not assumed).
- **Peak-capture metrics** (wave 20) — per scored window: ``peak_mae`` (MAE
  on the window's top-decile-by-actual days) and ``peak_recall`` (share of
  the window's top-5 actual days ranked in the forecast's own top-5),
  pooled per class with paired cluster-bootstrap CIs vs the routed and zero
  baselines — the headline answer to "peaks aren't captured".
- **Uncertainty** — per horizon: quantile HGBs (p10/p50/p90, pinball loss
  reported) plus a split-conformal ±q80 width calibrated on the selection
  origins, zero-clipped and sorted. Sparse (routed) series get an honest
  sparse band instead: P(any sale) + a quantile ladder of the training
  history, which cannot collapse to a zero-width interval.
- **Decision metric** — an order-up-to policy simulation (service level τ →
  order = quantile_τ of the forecast distribution; holding + stockout cost
  against actuals), champion vs seasonal-naive policy, per demand class, cost
  assumptions documented in the JSON. Wave 22 adds a newsvendor layer: the
  order IS the routed band's q-quantile (band ladder / sparse history ladder;
  the floor reads the same quantile of the seasonal-naive weekday
  distribution) under documented holding/stockout unit costs. Labelled a
  simulation — no savings claims.
- **Paired bootstrap** — every headline comparison (per-class champion-vs-floor
  and champion-vs-naive at h=7/h=14, model-rank gaps, routing before/after)
  carries a 95% cluster bootstrap CI over (series x scored test origins):
  series are resampled with replacement, one shared index draw per
  replication so differences stay paired (the pattern from projects/05 /10).
- **Wave-22 statistical candidates** — ``ma_28`` (rolling 28-day mean, flat),
  and the ADIDA pair ``adida_sba`` / ``adida_tsb`` (7-day temporal aggregation
  aligned to the origin so the 14-day window is exactly 2 buckets, SBA/TSB on
  the bucket series, within-week-profile disaggregation — see
  intermittent.adida_forecast). All three join the sparse routing pool.
- **Wave-22 rolling features** — the design adds a rolling block at the same
  target-h reference day as the peak/price blocks: rolling means over
  7/14/28 days and rolling stds over 14/28 (rmean7/rmean14/rmean28/rstd14/
  rstd28), so the boosters see trend/volatility state, not just levels.
- **Wave-22 hierarchy anchoring** — ``routed_reconciled`` (comparison-only):
  per country block the routed forecast is reconciled to the seasonal-naive
  anchor of the country's aggregated demand (a denser, independent signal),
  discrepancy allocated proportionally to the routed forecasts (fallback:
  training-window means; then no adjustment).
- **Wave-22 metrics** — ``rmae`` (candidate pooled MAE / floor pooled MAE) and
  per-candidate ``rmsse`` (M5 convention) per class and pooled; the decision
  block gains a newsvendor order-quantile cost layer (documented cost
  assumptions, no savings claims). The headline claim quotes rmae.
- **Wave-23 roadmap round** — the nowcast track's sparse interval is
  non-degenerate (predicted-zero rows take [0, history q80] instead of the
  zero-aware band's ±0 width — see probabilistic.sparse_history_band), and
  the multistep block gains a cost-aware routing arm
  (``routing.cost_aware``): the per-series pick minimises summed newsvendor
  cost on the selection origins at q=0.90, scored once on the test origins
  against the MAE-routed champion (MAE + newsvendor cost per class).

Outputs are merged into the track's metrics.json (``_multistep`` block — the
per-model nowcast blocks stay untouched), probabilistic.json (``multistep``
key, including per-candidate bands for the peak-capable models),
evaluation_metadata.json (``multi_horizon`` block) and seven figures
(unit-incompatible metrics never share an axis; three of them are the wave-20
peak-capture views).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from joblib import Parallel, delayed, parallel_config
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_json

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import _json_safe
from demand_forecasting.intermittent import SPARSE_CLASSES, classify_panel
from demand_forecasting.multistep_blocks import (
    _assemble_block,
    _bands,
    _bootstrap_suite,
    _growth_curves,
    _metadata_block,
    _per_horizon_metrics,
    _test_cells,
)
from demand_forecasting.multistep_constants import ML_SPARSE
from demand_forecasting.multistep_decision import _order_up_to
from demand_forecasting.multistep_features import (
    _calendar_features,
    multistep_origin_indices,
    panel_matrix,
    panel_price_matrix,
    split_origins,
)
from demand_forecasting.multistep_figures import _figures
from demand_forecasting.multistep_metrics import _peak_capture, _win_rates
from demand_forecasting.multistep_models import _score_origin
from demand_forecasting.multistep_routing import (
    _cost_aware_block,
    _route,
    _route_cost,
    _routed_cells,
    apply_hurdle_correction,
    choose_peak_weight,
    ensemble_weights,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Result container + main entry
# ---------------------------------------------------------------------------


@dataclass
class MultiStepResult:
    """Everything the multi-step track produced, plus the report figures."""

    block: dict[str, Any] = field(default_factory=dict)  # metrics.json "_multistep"
    probabilistic_block: dict[str, Any] = field(default_factory=dict)  # probabilistic.json
    metadata_block: dict[str, Any] = field(default_factory=dict)  # evaluation_metadata.json
    figures: dict[str, go.Figure] = field(default_factory=dict)


def run_multistep(
    settings: DemandSettings, config: ForecastConfig, panel: pl.DataFrame
) -> MultiStepResult:
    """Run the full direct multi-horizon track; returns JSON blocks + figures."""
    del settings  # artifact merging is the caller's job (evaluate.py)
    dates, series_ids, units = panel_matrix(panel)
    price = panel_price_matrix(panel, dates, series_ids)
    cal = _calendar_features(dates)
    horizons = list(config.multistep_horizons)
    n_series = len(series_ids)
    classes = classify_panel(units, series_ids)
    sparse = np.array([classes[s]["class"] in SPARSE_CLASSES for s in series_ids])

    origins = multistep_origin_indices(len(dates), config)
    selection, test = split_origins(origins, config)
    logger.info(
        "multistep: %d origins (%d selection + %d test), horizons %s, %d series, "
        "%d sparse (%.1f%%), price features %s",
        len(origins),
        len(selection),
        len(test),
        horizons,
        n_series,
        int(sparse.sum()),
        100.0 * sparse.mean(),
        "on" if price is not None else "off (neutral)",
    )
    # inner_max_num_threads=1: the workers run full-core already — letting
    # each estimator ALSO spawn its own thread pool (sklearn OpenMP, LightGBM)
    # oversubscribes the machine and every fit slows down several-fold
    with parallel_config("loky", inner_max_num_threads=1):
        scores = Parallel(n_jobs=-2)(
            delayed(_score_origin)(units, cal, o, horizons, config, (), price) for o in origins
        )
    by_origin = {s.origin: s for s in scores}

    # ---- peak-weight choice + hurdle zero-correction: SELECTION origins only --
    pw_choice = choose_peak_weight(by_origin, selection, horizons, units)
    correction = apply_hurdle_correction(by_origin, selection, horizons, units)

    # ---- routing: per-series best candidate on SELECTION origins only ----
    method_of = _route(by_origin, selection, horizons, units, sparse, n_series)

    # ---- cost-aware routing (wave 23): same contract, newsvendor-cost pick ----
    method_of_cost = _route_cost(by_origin, selection, horizons, units, sparse, n_series)

    # ---- convex ensemble: per-series weight on SELECTION origins only (no refits)
    ens = ensemble_weights(by_origin, selection, horizons, units, sparse, method_of, n_series)
    ens_ml_idx = np.array([ML_SPARSE.index(str(m)) for m in ens["ml_choice"]])

    # ---- long table over the TEST origins (scored once) ----
    cells = _test_cells(
        by_origin,
        test,
        horizons,
        units,
        sparse,
        method_of,
        series_ids,
        ens["weights"],
        ens_ml_idx,
    )
    class_of_series = np.array([classes[s]["class"] for s in series_ids])
    cells["class"] = class_of_series[cells["series"]]

    # ---- cost-aware routing arm: scored once on the test origins (wave 23) ----
    ca_cells = _routed_cells(by_origin, test, horizons, units, sparse, method_of_cost)
    cost_aware = _cost_aware_block(
        by_origin,
        selection,
        horizons,
        units,
        method_of,
        method_of_cost,
        ca_cells,
        cells,
        class_of_series,
        series_ids,
        config,
    )

    per_horizon = _per_horizon_metrics(cells, horizons)
    bands = _bands(by_origin, selection, test, horizons, units, sparse, cells)
    bootstrap = _bootstrap_suite(cells, horizons, config)
    growth = _growth_curves(cells, horizons)
    peak = _peak_capture(cells, test, horizons, n_series, config)
    win_rates = _win_rates(cells, horizons, config)
    class_of_series = np.array([classes[s]["class"] for s in series_ids])
    decision = _order_up_to(
        by_origin,
        selection,
        horizons,
        units,
        sparse,
        method_of,
        cells,
        class_of_series,
        config,
        dates,
    )
    block = _assemble_block(
        dates,
        origins,
        selection,
        test,
        horizons,
        classes,
        sparse,
        method_of,
        per_horizon,
        bands,
        bootstrap,
        growth,
        decision,
        cells,
        series_ids,
        config,
        correction,
        peak,
        win_rates,
        pw_choice,
        ens,
        cost_aware,
    )
    figures = _figures(block, horizons, bands["json"], cells, test, n_series)
    result = MultiStepResult(
        block=block,
        probabilistic_block=bands["json"],
        metadata_block=_metadata_block(block, config),
        figures=figures,
    )
    logger.info(
        "multistep: pooled MAE h1=%.3f -> h14=%.3f (champion), coverage pooled=%.3f (%s)",
        per_horizon[horizons[0]]["champion"]["mae"],
        per_horizon[horizons[-1]]["champion"]["mae"],
        bands["json"]["pooled_coverage"],
        bands["json"]["pooled_verdict"],
    )
    return result


# ---------------------------------------------------------------------------
# Artifact merging (called from evaluate.py / probabilistic.py / cli.py)
# ---------------------------------------------------------------------------


def merge_metrics_json(settings: DemandSettings, result: MultiStepResult) -> None:
    """Add the ``_multistep`` block to the track's metrics.json.

    The per-model nowcast blocks (and ``_meta``) are untouched; keys starting
    with ``_`` are ignored by the demo payload's run parser, so the payload
    keeps working unchanged.
    """
    path = Path(settings.reports_dir) / "metrics.json"
    metrics: dict[str, Any] = json.loads(path.read_text())
    metrics["_multistep"] = result.block
    path.write_text(json.dumps(_json_safe(metrics), indent=2))
    logger.info("multistep metrics merged -> %s", path)


def merge_evaluation_metadata(settings: DemandSettings, result: MultiStepResult) -> None:
    """Add the ``multi_horizon`` protocol block to evaluation_metadata.json."""
    path = Path(settings.reports_dir) / "evaluation_metadata.json"
    meta: dict[str, Any] = json.loads(path.read_text())
    meta["multi_horizon"] = result.metadata_block
    path.write_text(json.dumps(_json_safe(meta), indent=2))
    logger.info("multistep evaluation metadata merged -> %s", path)


def save_multistep_figures(settings: DemandSettings, result: MultiStepResult) -> None:
    """Persist the multi-step figure JSONs next to the other figures."""
    out_dir = Path(settings.reports_dir) / "figures"
    for name, fig in result.figures.items():
        save_json(fig, out_dir / f"{name}.json")
