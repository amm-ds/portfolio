# 02 · Hierarchical Demand Forecasting

**Domain:** time-series forecasting · **Data:** seeded synthetic retail hierarchy
(4 stores × 6 products × 730 days, `portfolio_core.synthetic.retail_hierarchy`) ·
**Status:** working showcase on the standard platform (flagships: [01](../01-rag-agent), [07](../07-open-data-mobility))

## Problem

A retailer sells 6 products in 4 stores and needs **per-store-product daily unit
forecasts**. The hierarchy is small enough to model globally but structured
enough to demand honest validation: demand has trend, weekly seasonality and
store/product-specific levels, so a random train/test split would leak the
future into the past and overstate accuracy. The deliverable is a reproducible
pipeline that generates the data, validates it, engineers leakage-safe
features, and compares a linear baseline against a gradient-boosted model
under an embargoed expanding-window backtest.

## Design

See [DESIGN.md](DESIGN.md) for the full requirements/options/decisions log.
Summary:

- **Data**: platform-seeded synthetic panel (`seed=42`, 730 days → 17,520 rows),
  gated by `DQReport` (null-rate, range, freshness) and versioned by a
  `DatasetContract` with SHA-256 (`data/dataset.json`). A real-data track
  (UCI Online Retail II) is implemented behind `--data-source uci` — the
  headline results below come from it; synthetic stays the default so CI
  runs offline.
- **Features** (`features.py`): lags `[1, 7, 14]` built with `shift` **per
  series** (never the current row), plus calendar features (day-of-week,
  weekend, month, week, day-of-year sin/cos) and a linear trend counter.
  Undefined-lag rows are dropped, never imputed.
- **Models** (`model.py`): two deterministic naive floors — `naive_mean`
  (global train mean) and `naive_last` (per-series persistence) — two
  statistical baselines — `seasonal_naive` (lag-7, same weekday last week)
  and per-series ETS (statsmodels Holt-Winters, damped trend + weekly
  seasonality, fallback chain to seasonal naive for short/failing series,
  documented + tested) — plus global models with one-hot series id: `ridge`
  (Ridge inside a `Pipeline` with `StandardScaler` + one-hot), three
  boosting arms — `hgb` (default sklearn), `hgb_tuned` (production),
  `xgb_tuned` (XGBoost) and `lgbm_tuned` (LightGBM),
  the latter two Optuna-tuned mirrors of the HPO space — and `temporal_net`
  (hand-written PyTorch embedding+MLP, `temporal.py`).
  One artefact for the whole hierarchy, new series handled via
  `handle_unknown="ignore"`.
- **HPO** (`hpo.py`): seeded Optuna studies (TPESampler seed 42, median pruning)
  per booster arm — sklearn HGB (6 hyperparams, 56 trials), XGBoost (6, 25) and
  LightGBM (5, 25) — with the objective = mean MAE over
  the *same* date-aligned CV folds as the backtest. Best params (CV MAE 8.5291)
  are persisted to `data/hpo_best.json` and mirrored into
  `ForecastConfig.hgb_tuned` defaults + `params.yaml`. Resumable SQLite
  storage with per-trial checkpointing; run via `cli hpo` (separate dvc stage
  before `train`, deliberately not part of `cli all`).
- **Reconciliation** (`reconcile.py`): store-level (parent) forecasts from the
  tuned model are compared against summed store-product (children) forecasts;
  a scalar MinT-lite shrinkage `w`, grid-estimated on the embargoed previous
  fold, redistributes the parent-child discrepancy. Coherence after adjustment
  is exactly `(1-w)` of the incoherence before (property-tested).
- **Real-data track** (`uci.py`): UCI Online Retail II activated behind
  `--data-source uci` — checksum-pinned download (sha256 in `params.yaml`),
  dependency-free XLSX streaming parser (stdlib zipfile/iterparse), 2009-2010
  sheet parsed to 525,461 transactions, aggregated to a bounded daily panel
  (top 8 countries as stores × top 200 stock codes as products, 374 days,
  405,416 rows, 89% zero share — genuinely intermittent demand). Sales lines
  only (returns/cancellations excluded, documented). Synthetic stays the
  default so CI runs offline. The full data-generating process — filtering,
  aggregation, geography, caveats — is documented in
  [reports_uci/dataset_metadata.json](reports_uci/dataset_metadata.json)
  (emitted by `prepare`) and summarised under **Data-generating process**
  below. The forecast target is **the next 14 days of daily units per
  country-product series** (top 8 countries × top 200 products by volume),
  aggregated from cleaned Online Retail II transactions (cancellations removed).
- **Probabilistic forecasts** (`probabilistic.py`): quantile HGB (p10/p50/p90)
  on the tuned config plus a split-conformal band calibrated on the early
  folds; empirical coverage reported against the 80% target, with a band
  figure for the two highest-volume series.
- **Validation** (`evaluate.py`): `TimeSeriesCV` (4 expanding-window folds,
  7-day embargo gap) over the dated feature rows, folds mapped to rows so
  no date block straddles train/validation. **Frozen holdout protocol**
  (`rolling_origin_holdout_v1`): the last origin is the test window — model
  selection (champion pick) pools folds 1..n-1 only, every candidate is
  scored once on the test window, and the committed headline metrics are the
  test-window numbers. The protocol, the exact `selection_used_origins` vs
  `test_origin`, the within-train-window preprocessing guarantee and every
  metric definition are emitted to
  [reports_uci/evaluation_metadata.json](reports_uci/evaluation_metadata.json);
  the previous all-fold pooled headline is retained per model under
  `legacy_pooled_*` in metrics.json. Metrics from
  `portfolio_eval.ml.regression_metrics` (MAE/RMSE/MAPE) plus MASE, bias,
  zero-safe WAPE, per-fold MAEs (std/range) and per-horizon (h=1..14)
  MAE/MASE on the test window's final 14 days.

## Data-generating process (UCI track)

`reports_uci/dataset_metadata.json` is the machine-readable audit anchor;
the summary (all of it implemented in `uci.py` — the doc exists because the
review demanded the pipeline's data contract be stated explicitly):

- **Source**: UCI Online Retail II, `online+retail+ii.zip`
  (https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip),
  sha256-pinned in `params.yaml`, sheet *Year 2009-2010*, free for research
  (Chen, Gallino & Li 2012, *Management Science*).
- **Cancellation filtering**: sales lines only — rows with `Quantity > 0`;
  cancellations/returns (negative-quantity lines) are removed, blank stock
  codes dropped. Returns are a separate business process; net-of-returns
  demand would double-count reverse logistics.
- **Quantity handling**: daily sum of line quantities per
  (date, country, stock_code) → the panel's integer `units`; `price` is the
  mean line price of the day (carried for reference, not a model target).
- **Geography / products**: top 8 countries by unit volume become `stores`,
  top 200 stock codes become `products`; everything else is dropped.
- **Daily aggregation**: one row per (date, country, stock_code), reindexed
  to the complete daily calendar between first and last observed dates;
  missing day-series combinations are zero-filled (price forward-filled).
  Observed range: 2009-12-01..2010-12-09 (374 days → 405,416 rows after the
  top-N bounding, 89% zero share).
- **Caveat — zeros**: zero-sales days may be missing rather than true zero
  demand: the source has **no trading calendar**, so a zero-filled day can
  mean "closed or not trading" as easily as "no demand". Models must live
  with that ambiguity; it is also why MAPE is not decision-grade here.

## Synthetic track — CI fast path (`data_source: synthetic`, seed 42)

The synthetic hierarchy (24 series, clean trend + weekly seasonality) is the
**CI/offline path**: fully seedable, byte-reproducible, no network. It exists
so every gate in this repo runs hermetically; the headline results live on the
real-data track below. Ladder below is scored on the **final holdout
window** (last rolling origin), champion selected on origins 1..n-1 only —
note what clean data does to the statistical baselines:

| model | MAE (units) | RMSE (units) | MAPE (%) | MASE |
|---|---|---|---|---|
| naive_mean (global train mean) | 35.946 | 48.639 | 48.26 | 3.755 |
| naive_last (persistence, y(t-1)) | 16.223 | 22.238 | 19.47 | 1.695 |
| seasonal_naive (lag-7) | 11.780 | 16.689 | 13.98 | 1.231 |
| **ETS (Holt-Winters, damped+weekly)** | **8.924** | **12.691** | **10.37** | **0.932** |
| ridge (linear baseline) | 9.705 | 13.706 | 11.92 | 1.014 |
| hgb (default HGB) | 9.549 | 13.380 | 11.58 | 0.998 |
| hgb_tuned (Optuna, 56 trials) | 9.472 | 13.269 | 11.51 | 0.990 |
| xgb_tuned (Optuna, 25 trials) | 9.525 | 13.372 | 11.59 | 0.995 |
| lgbm_tuned (Optuna, 25 trials) | 9.341 | 13.101 | 11.31 | 0.976 |
| temporal_net (PyTorch emb+MLP) | 9.244 | 12.908 | 11.38 | 0.966 |

On clean synthetic data **ETS wins outright** (MASE 0.932) — a correctly
specified Holt-Winters model is exactly the right class for smooth
trend + weekly seasonality, and the boosters only approximate it. This is the
deliberate counterpoint to the real track, where intermittency flips the
ordering. Two honest notes from the frozen holdout: on this one test window
`temporal_net` posts the lowest ML MAE (9.244, a hair ahead of `lgbm_tuned`
9.341 — a gap well inside the fold-to-fold spread), and every run's
test-window MAE is higher than its pooled legacy number because the last fold
carries the most trend drift; both are one-window estimates, not new
champions.

Key findings:

- Against the stronger naive floor (`naive_last`), the champion cuts test-window
  MAE by **45.0%** (16.22 → 8.92 units); against `naive_mean` the reduction is
  75.2%. Persistence loses because demand has strong weekly seasonality and a
  rising trend: yesterday's value systematically misses weekday effects and
  never anticipates the trend — the lag/calendar features plus a nonlinear
  model capture exactly those two structure components.
- **LightGBM edges out the incumbent HGB config** on the pooled selection folds
  (legacy pooled MAE 8.413 vs 8.529) and stays the best ML run on the
  synthetic test window (9.341 vs 9.472). `xgb_tuned` is a statistical wash vs
  `hgb_tuned`. Three independent boosting libraries land within 1.5% of each
  other — on this panel the marginal value of further model-family search is
  small, and honest reporting says so.
- **HPO earned a modest but real gain** across arms: 56 seeded trials improved
  the sklearn HGB from 8.619 to 8.529 (-1.0%) pooled over all folds (legacy
  numbers); see the `hpo_history` / `hpo_importance` figures (per-arm
  variants for xgb/lgbm).
- **The neural model is competitive but not the champion.** `temporal_net`
  tracks ridge on the selection folds and lands the best ML test-window MAE
  (9.244) — but ETS, selected on origins 1..n-1, still wins outright. On small
  tabular lag features, gradient-boosted trees and a well-specified
  Holt-Winters remain the tools to beat; reported honestly.
- **Reconciliation (MinT-lite, test window, store level)**: the grid estimator
  chose w=0.00 this run — the parent-level model suffers the same fold-4 drift
  as the children, so no trust is placed in it. Store-level MAE stayed
  23.814 and incoherence |parent forecast − Σ children| stayed 27.340
  (exactly ×(1−w), the tested coherence property). Structural coherence is
  guaranteed; accuracy gains from reconciliation need a drift-robust parent
  model — a documented, quantified caveat.
- Where the gains plateau: all runs degrade on the last fold as the injected
  trend lifts demand, but the improvement ratio over persistence is stable
  across folds. The residual ~9-unit test-window MAE is mostly day-over-day
  noise, which no lag feature can remove.

Per-fold MAE (see the `fold_stability` figure for the full ten-run view;
fold 4 is the holdout window):

| fold | naive_mean | naive_last | ridge | hgb | hgb_tuned | temporal_net |
|---|---|---|---|---|---|---|
| 1 | 27.748 | 12.853 | 9.280 | 7.860 | 7.728 | 9.229 |
| 2 | 30.266 | 13.800 | 8.572 | 8.149 | 8.083 | 9.837 |
| 3 | 33.086 | 15.029 | 8.907 | 8.916 | 8.834 | 9.053 |
| 4 | 35.946 | 16.223 | 9.705 | 9.549 | 9.472 | 9.244 |

hgb_tuned improves on hgb in **every** fold; on the holdout window
temporal_net finally leads the ML pack (9.244) without threatening ETS.

## Headline results — real data (UCI Online Retail II, `cli all --data-source uci`)

Real transactions, same pipeline, same embargoed rolling-origin backtest with
the frozen holdout: 525,461 sales lines parsed from the 2009-2010 sheet → top
8 countries × top 200 products, 374 days (2009-12-01..2010-12-09), 405,416
panel rows, **89.2% zero share** — classical intermittent demand. The table
below is scored on the **test window** (final origin, 2010-10-01..2010-12-09,
70 days); the champion was selected on origins 1..3 only. **MAE/MASE lead;
MAPE is reported but not decision-grade here** (near-zero actuals inflate it
to 184–328% for every run; the zero-demand caveat is in the
data-generating-process section above and in the figure captions):

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_mean | 12.475 | 74.699 | 90.3% | 1.382 |
| naive_last (persistence) | 11.505 | 99.548 | 327.6% | 1.331 |
| seasonal_naive (lag-7) | 11.323 | 114.921 | 305.4% | 1.310 |
| ETS (Holt-Winters, damped+weekly) | 11.471 | 80.827 | 302.7% | 1.338 |
| ridge (linear baseline) | 12.384 | 72.680 | 221.7% | 1.395 |
| hgb (default sklearn) | 9.565 | 71.700 | 260.3% | 1.085 |
| **hgb_tuned (Optuna, 56 trials) ← best** | **9.545** | **71.847** | 230.0% | **1.078** |
| xgb_tuned (Optuna, 25 trials) | 9.804 | 73.287 | 277.2% | 1.118 |
| lgbm_tuned (Optuna, 25 trials) | 9.409 | 71.360 | 272.3% | 1.076 |
| temporal_net (PyTorch emb+MLP) | 11.770 | 71.849 | 183.6% | 1.305 |

What the audit-driven statistical baselines reveal on **real** data:

- **They do not beat the boosters here** — the mirror image of the synthetic
  track, where ETS wins outright. `seasonal_naive` (11.323 test MAE, 1.310
  MASE) is the strongest floor and a serious contender — no run clears MASE 1
  on this test window: it covers the holiday quarter (Oct–Dec 2010), where
  bulk spikes lift every model above seasonal-naive parity. ETS *loses* to
  its own seasonal naive (11.471 vs 11.323, MASE 1.338): Holt-Winters assumes
  every series is smooth and seasonal, and 89% zeros plus bulk spikes break
  that assumption (the fallback chain is documented and unit-tested).
- **Cross-track transfer is the honest punchline, and it reversed under the
  frozen protocol**: the old pooled ladder claimed the synthetic ML champion
  `lgbm_tuned` "drops to fourth on real data" (9.600). On the one-shot test
  window `lgbm_tuned` actually posts the **best** MAE of all runs (9.409,
  ahead of the selection champion `hgb_tuned` at 9.545 — a 1.4% gap inside
  the fold-to-fold spread, so one window cannot dethrone the protocol's
  pick), while the synthetic overall champion `ets` ranks 6th on real data
  (11.471). Configs tuned on clean synthetic data still behave differently on
  intermittent real demand; neither pooled nor single-window rankings should
  be read as more than what they are. This is why both tracks stay in the
  repo side by side.
- **Ridge is no longer the collapse story** (12.384 test MAE — mid-pack on
  this window, though its pooled legacy 16.734 was behind every floor) and
  **MAPE/RMSE are not decision metrics** on this data (184–328% MAPE; RMSE ≫
  MAE from wholesale spikes). MAE, MASE, bias and WAPE are the numbers to
  plan with — the champion's test-window bias is −1.444 units (mild
  over-forecasting) with WAPE 1.142.
- **Reconciliation pays off on the test window**: w=0.60 — incoherence 500.0 →
  200.0 (exactly ×(1−w), property-tested); store-level MAE 738.7 → 676.4
  (−8.4% this run — coherence is a guarantee, accuracy gains depend on
  parent-model quality, stated plainly; the shrinkage grid is estimated on
  origin 2 and the store-level backtest re-fits HGB, so w jitters
  run-to-run within the documented OpenMP tolerance).
- **Probabilistic (target 80% band)** — coverage AND average width on the
  test window's final 14 days (h=1..14):

  | track | quantile band (pooled over folds) | zero-aware split-conformal, horizon set | avg width | verdict |
  |---|---|---|---|---|
  | synthetic | 0.727 | 0.741 | 26.49 units | optimistic (under-covers) |
  | UCI real | 0.919 | 0.861 | 0.00 units | conservative — but degenerate |

  Honest reading: on clean synthetic data the band under-covers (0.741 vs
  0.80 target → optimistic). On intermittent demand the champion's median
  sits on the zero atom for ~100% of test-window rows, so the zero-aware
  band collapses to the point forecast (avg width 0.00 units) and its 0.861
  "coverage" only means 86.1% of actuals were exactly zero — the conservative
  verdict is a degenerate band, not a useful one. The quantile band covers
  0.919 pooled precisely because it is wide where the conformal band is
  empty. Per-bin calibration is explicit in `probabilistic.json` (per-horizon
  coverage and width arrays, `calibration_verdict`) and the figure states the
  achieved coverage and width; per-series (or clustered) conformal remains
  the fix direction.

Figures (HTML + JSON per track, `reports/figures/` synthetic,
`reports_uci/figures/` real) — the audit list:

- `forecast_fan` (real track) — p10/p50/p90 fan + actual for the two
  highest-volume series, last fold, with takeaway
- `coherence_heatmap` — per-store |parent − Σ children| before/after the
  MinT-lite adjustment, annotated
- `fold_stability` — the error-by-fold panel (drift visible per run)
- `forecast_vs_actual` — champion vs strongest naive on example series
- `metrics_bars` / `eda_series_overview` / `eda_units_distribution` /
  `hpo_history` / `hpo_importance` / `reconciliation_coherence` /
  `probabilistic_band` as before

Artifacts: per track, `reports*/metrics.json` (10 runs: test-window MAE/RMSE/
MAPE/MASE + bias/WAPE + fold MAEs + per-horizon arrays + `legacy_pooled_*`,
and a `_meta` protocol block), `evaluation_metadata.json`, `report.html`,
`reconciliation.json`, `probabilistic.json` (coverage AND width per horizon,
`calibration_verdict`); the UCI track also emits `dataset_metadata.json`.
`data_uci/` (panel 405,416 rows, contract, models) and `data/` (synthetic).
Runtime (this machine, `cli evaluate`): synthetic ≈ **1.5 min** with
probabilistic; UCI ≈ **7 min** (ETS fits 1,084 series per fold); 6/6 DQ gates
pass on both tracks.

## Reproduce

```bash
# from the repo root, inside the workspace venv
uv run python -m demand_forecasting.cli all            # synthetic pipeline (~2 min)
uv run python -m demand_forecasting.cli all --data-source uci   # real-data track (~8 min, fetches once)
uv run python -m demand_forecasting.cli hpo            # Optuna HPO (minutes; resumable; --model xgb|lgbm)
uv run dvc metrics show                                 # declared metrics (reports/metrics.json)
# or stage by stage (mirrors dvc.yaml)
uv run python -m demand_forecasting.cli prepare
uv run python -m demand_forecasting.cli features
uv run python -m demand_forecasting.cli train
uv run python -m demand_forecasting.cli evaluate
# or
dvc repro projects/02-demand-forecasting
```

Tests run fully offline against seeded synthetic fixtures:

```bash
uv run pytest projects/02-demand-forecasting -q
```

## What this demonstrates for a client

- **Leakage discipline as a first-class concern**: features shifted, not
  centered; embargoed expanding-window backtest instead of a random split;
  per-fold stability reported alongside the headline metric so drift is
  visible before it hurts.
- **Baseline-first modelling**: naive floors (global mean, persistence,
  weekly seasonal-naive) and a per-series ETS anchor every claim; the trained
  models must *earn* their complexity — on the real-data test window the
  selection champion `hgb_tuned` beats the strongest floor (`seasonal_naive`)
  by 15.7% MAE (9.545 vs 11.323), and the frozen protocol is precisely what
  makes that number a measurement instead of a hope.
- **Model selection as an engineering discipline**: HPO optimises on the same
  embargoed folds it is judged on, the champion is picked on origins 1..n-1
  and scored once on the final holdout, the un-tuned model stays in the
  ladder for comparison, and the neural candidate is reported with its honest
  verdict rather than silently dropped.
- **Hierarchy handling without a per-series zoo**: one global model with
  series identity captures 24 series in a single deployable artefact.
- **Contract-governed data**: every dataset carries a versioned identity card
  and must pass DQ gates before any model trains — the pipeline fails loudly,
  not silently.
- **Reproducibility**: seeded data, pydantic-validated config, dvc stages,
  offline tests — results regenerate exactly on any machine with the repo.

## Roadmap

Delivered: UCI real-data track (now the headline), probabilistic forecasts
(quantile HGB + split-conformal), Optuna HPO across three boosting arms, and
the wave-13 audit items — statistical baselines (`seasonal_naive` + per-series
damped Holt-Winters ETS with documented fallbacks) and **MASE** on both tracks,
plus the fan-chart/coherence-heatmap/error-by-fold figure set. What remains:

1. **Calibrated intervals for intermittent demand**: per-series (or clustered)
   conformal calibration and zero-inflated interval models — the zero-aware
   band under-covers on synthetic (0.741 coverage at 0.80 target) and is
   degenerate on real data (avg width 0.00 on the test window: the median
   sits on the zero atom).
2. **Origin-stacked multi-horizon bands**: per-horizon coverage/width is now
   reported descriptively on the test window (h=1..14); *separately
   calibrated* per-origin bands still need a horizon-stacked target frame.
3. **Full MinT reconciliation**: covariance projection once the UCI track grows
   a product-category hierarchy.
4. **Returns-aware demand**: model cancellations/returns as their own flow
   instead of excluding them, for net-demand forecasting.
