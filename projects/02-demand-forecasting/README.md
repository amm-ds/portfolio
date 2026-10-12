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
  (UCI Online Retail II) is documented in DESIGN.md but not implemented.
- **Features** (`features.py`): lags `[1, 7, 14]` built with `shift` **per
  series** (never the current row), plus calendar features (day-of-week,
  weekend, month, week, day-of-year sin/cos) and a linear trend counter.
  Undefined-lag rows are dropped, never imputed.
- **Models** (`model.py`): two deterministic naive floors — `naive_mean`
  (global train mean) and `naive_last` (per-series persistence) — plus global
  models with one-hot series id: `ridge` (Ridge inside a `Pipeline` with
  `StandardScaler` + one-hot) and `hgb` (`HistGradientBoostingRegressor`).
  One artefact for the whole hierarchy, new series handled via
  `handle_unknown="ignore"`.
- **Validation** (`evaluate.py`): `TimeSeriesCV` (4 expanding-window folds,
  7-day embargo gap) over the 716 dated feature rows, folds mapped to rows so
  no date block straddles train/validation. Metrics from
  `portfolio_eval.ml.regression_metrics` on pooled out-of-fold predictions.

## Results (seed 42, real run of `demand_forecasting.cli all`)

Pooled out-of-fold metrics across all 4 folds and 24 series:

| model | MAE (units) | RMSE (units) | MAPE (%) | Δ MAE vs naive_last |
|---|---|---|---|---|
| naive_mean (global train mean) | 31.762 | 42.543 | 49.02 | — (worst floor) |
| naive_last (persistence, y(t-1)) | 14.476 | 19.881 | 19.28 | — (strongest naive) |
| ridge (linear baseline) | 9.116 | 12.705 | 12.44 | -37.0% |
| **hgb (gradient boosting)** | **8.619** | **12.178** | **11.43** | **-40.5%** |

Against the stronger naive floor (`naive_last`), the best model cuts MAE by
**40.5%** (14.48 → 8.62 units) and MAPE by 7.8 points (19.3% → 11.4%); against
`naive_mean` the reduction is 72.9%. Why persistence loses here: demand has
strong weekly seasonality and a rising trend, so yesterday's value
systematically misses weekday effects (a Monday forecast made from Sunday's
number starts ~25% off before noise) and never anticipates the trend. The
lag/calendar features plus a nonlinear model capture exactly those two
structure components.

Where the gains plateau: per-fold MAE below. All runs degrade on the last
fold as the injected trend lifts demand, but the improvement ratio is stable —
hgb beats naive_last by 38.8–41.1% in every fold — because drift inflates
both errors equally. The residual ~8.6-unit pooled MAE is mostly
day-over-day noise, which no lag feature can remove; that noise floor is what
a neural or reconciliation-based model would have to beat (see Roadmap).

| fold | naive_mean | naive_last | ridge | hgb |
|---|---|---|---|---|
| 1 | 27.748 | 12.853 | 9.280 | 7.860 |
| 2 | 30.266 | 13.800 | 8.572 | 8.149 |
| 3 | 33.086 | 15.029 | 8.907 | 8.916 |
| 4 | 35.946 | 16.223 | 9.705 | 9.549 |

Figures (HTML + JSON for the showcase app) in `reports/figures/`:

- `eda_series_overview` — raw daily units for 4 sample series (trend + weekly
  seasonality visible)
- `eda_units_distribution` — histogram of daily units over the panel
- `forecast_vs_actual` — actual vs **hgb** vs **naive_last** on the last fold
  for `store_0|product_0` and `store_3|product_5` (the naive overlay shows
  where the model earns its improvement)
- `metrics_bars` — grouped MAE/RMSE/MAPE comparison across all four runs
- `fold_stability` — MAE per fold per model

Other artifacts: `reports/metrics.json`, `reports/report.html`,
`data/panel.parquet` (17,520 rows), `data/features.parquet` (17,184 rows × 17
cols), `data/models.pkl` (all four models refit on full history),
`data/dataset.json` (dataset identity card). Full pipeline runtime ≈ **17 s**
on this machine; 6/6 DQ gates pass.

## Reproduce

```bash
# from the repo root, inside the workspace venv
uv run python -m demand_forecasting.cli all            # full pipeline
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
- **Baseline-first modelling**: two naive floors (global mean, persistence)
  anchor every claim; the trained models must *earn* their complexity —
  gradient boosting beats persistence by 40.5% MAE, the linear baseline by
  37.0%, an honest, quantified trade-off.
- **Hierarchy handling without a per-series zoo**: one global model with
  series identity captures 24 series in a single deployable artefact.
- **Contract-governed data**: every dataset carries a versioned identity card
  and must pass DQ gates before any model trains — the pipeline fails loudly,
  not silently.
- **Reproducibility**: seeded data, pydantic-validated config, dvc stages,
  offline tests — results regenerate exactly on any machine with the repo.

## Roadmap

Planned deepening, in priority order:

1. **Optuna HPO** for `hgb` (learning rate, max depth, min samples leaf) —
   dependency already declared; search budget and pruning strategy TBD.
2. **Real-data track**: UCI Online Retail II via `portfolio_core.io.fetch`
   with checksum pinning (DESIGN.md documents the mapping from invoice lines
   to this panel schema).
3. **Hierarchical reconciliation**: forecast store/product levels, then
   reconcile to category/total with MinT-style projection so every level of
   the hierarchy adds up.
4. **Probabilistic forecasts**: quantile regression or conformal intervals on
   top of the backtest residuals for inventory safety-stock sizing.
