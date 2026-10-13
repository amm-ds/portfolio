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
  `StandardScaler` + one-hot), `hgb` (default `HistGradientBoostingRegressor`),
  `hgb_tuned` (production HGB, hyperparameters from Optuna HPO), and
  `temporal_net` (hand-written PyTorch embedding+MLP, `temporal.py`).
  One artefact for the whole hierarchy, new series handled via
  `handle_unknown="ignore"`.
- **HPO** (`hpo.py`): seeded Optuna study (TPESampler seed 42, median pruning,
  56 complete trials) over learning_rate, max_iter, max_leaf_nodes,
  min_samples_leaf, l2_regularization, max_features; objective = mean MAE over
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
- **Validation** (`evaluate.py`): `TimeSeriesCV` (4 expanding-window folds,
  7-day embargo gap) over the 716 dated feature rows, folds mapped to rows so
  no date block straddles train/validation. Metrics from
  `portfolio_eval.ml.regression_metrics` on pooled out-of-fold predictions.

## Results (seed 42, real run of `demand_forecasting.cli all`)

Pooled out-of-fold metrics across all 4 folds and 24 series — the full run
ladder from naive floors to tuned and neural models:

| model | MAE (units) | RMSE (units) | MAPE (%) | Δ MAE vs naive_last |
|---|---|---|---|---|
| naive_mean (global train mean) | 31.762 | 42.543 | 49.02 | — (worst floor) |
| naive_last (persistence, y(t-1)) | 14.476 | 19.881 | 19.28 | — (strongest naive) |
| ridge (linear baseline) | 9.116 | 12.705 | 12.44 | -37.0% |
| hgb (default HGB) | 8.619 | 12.178 | 11.43 | -40.5% |
| **hgb_tuned (Optuna HPO)** | **8.529** | **12.071** | **11.34** | **-41.1%** |
| temporal_net (PyTorch emb+MLP) | 9.341 | 12.756 | 13.41 | -35.5% |

Key findings:

- Against the stronger naive floor (`naive_last`), the tuned model cuts MAE by
  **41.1%** (14.48 → 8.53 units) and MAPE by 7.9 points (19.28% → 11.34%);
  against `naive_mean` the reduction is 73.2%. Persistence loses because
  demand has strong weekly seasonality and a rising trend: yesterday's value
  systematically misses weekday effects and never anticipates the trend — the
  lag/calendar features plus a nonlinear model capture exactly those two
  structure components.
- **HPO earned a modest but real gain**: 56 seeded trials improved pooled CV
  MAE from 8.619 (default) to 8.529 (-1.0%). The search favoured smaller trees
  (max_leaf_nodes 25), a strong min_samples_leaf (48), a sub-linear learning
  rate (0.083) and feature subsampling (max_features 0.53) — heavily
  regularised ensembles; see the `hpo_history` / `hpo_importance` figures.
- **The neural model did not win.** `temporal_net` lands behind even the
  linear ridge baseline (MAE 9.34 vs 9.12; hgb_tuned 8.53). On small tabular
  lag features with 730 days of history, gradient-boosted trees remain the
  right tool; a sequence model over raw windows is the roadmap answer —
  reported honestly rather than tuned until it wins.
- **Reconciliation (MinT-lite, last fold, store level)**: the grid estimator
  chose w=0.05 — the parent-level model suffers the same fold-4 drift as the
  children, so barely any trust is placed in it. Store-level MAE improved
  23.892 → 23.837 and incoherence |parent forecast − Σ children| fell
  24.125 → 22.919 (exactly ×(1−w), the tested coherence property). Structural
  coherence is guaranteed; accuracy gains from reconciliation need a
  drift-robust parent model — a documented, quantified caveat.
- Where the gains plateau: all runs degrade on the last fold as the injected
  trend lifts demand, but the improvement ratio over persistence is stable
  across folds. The residual ~8.5-unit pooled MAE is mostly day-over-day
  noise, which no lag feature can remove.

Per-fold MAE (see the `fold_stability` figure for the full six-run view):

| fold | naive_mean | naive_last | ridge | hgb | hgb_tuned | temporal_net |
|---|---|---|---|---|---|---|
| 1 | 27.748 | 12.853 | 9.280 | 7.860 | 7.728 | 9.229 |
| 2 | 30.266 | 13.800 | 8.572 | 8.149 | 8.083 | 9.837 |
| 3 | 33.086 | 15.029 | 8.907 | 8.916 | 8.834 | 9.053 |
| 4 | 35.946 | 16.223 | 9.705 | 9.549 | 9.472 | 9.244 |

hgb_tuned improves on hgb in **every** fold; temporal_net tracks ridge but
never leads.

Figures (HTML + JSON for the showcase app) in `reports/figures/`:

- `eda_series_overview` / `eda_units_distribution` — raw-panel EDA
- `forecast_vs_actual` — actual vs **hgb_tuned** vs **naive_last** on the last
  fold, with a takeaway subtitle quantifying the improvement on that fold
- `metrics_bars` — grouped MAE/RMSE/MAPE comparison across all six runs
- `fold_stability` — MAE per fold per model
- `hpo_history` / `hpo_importance` — Optuna optimization history and
  hyperparameter importance
- `reconciliation_coherence` — per-store parent actual vs Σ children
  before/after the MinT-lite adjustment

Other artifacts: `reports/metrics.json`, `reports/report.html`,
`reports/reconciliation.json`, `data/panel.parquet` (17,520 rows),
`data/features.parquet` (17,184 rows × 17 cols), `data/models.pkl` (all six
models refit on full history), `data/hpo_best.json` (+ `hpo_study.db`),
`data/dataset.json` (dataset identity card). Full pipeline runtime ≈ **1 min**
unloaded (≈ 6 min under heavy multi-agent load); 6/6 DQ gates pass.

## Reproduce

```bash
# from the repo root, inside the workspace venv
uv run python -m demand_forecasting.cli all            # full pipeline (~1 min)
uv run python -m demand_forecasting.cli hpo            # Optuna HPO (minutes; resumable)
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
  tuned gradient boosting beats persistence by 41.1% MAE, the linear baseline
  by 6.4%, an honest, quantified trade-off.
- **Model selection as an engineering discipline**: HPO optimises on the same
  embargoed folds it is judged on, the un-tuned model stays in the ladder for
  comparison, and the neural candidate is reported with its honest verdict
  rather than silently dropped.
- **Hierarchy handling without a per-series zoo**: one global model with
  series identity captures 24 series in a single deployable artefact.
- **Contract-governed data**: every dataset carries a versioned identity card
  and must pass DQ gates before any model trains — the pipeline fails loudly,
  not silently.
- **Reproducibility**: seeded data, pydantic-validated config, dvc stages,
  offline tests — results regenerate exactly on any machine with the repo.

## Roadmap

Planned deepening, in priority order:

1. **Sequence model**: temporal_net's honest loss to the tree ensemble is the
   case for a raw-window model (small LSTM/TCN over the last k days) instead
   of hand-built lag features — the clearest next experiment.
2. **Real-data track**: UCI Online Retail II via `portfolio_core.io.fetch`
   with checksum pinning (DESIGN.md documents the mapping from invoice lines
   to this panel schema).
3. **Deeper reconciliation**: full MinT covariance projection across the whole
   hierarchy, and drift-robust parent models so the reconciled level is as
   trustworthy as the children.
4. **Probabilistic forecasts**: quantile regression or conformal intervals on
   top of the backtest residuals for inventory safety-stock sizing.
