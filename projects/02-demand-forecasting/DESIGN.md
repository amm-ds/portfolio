# DESIGN — 02 · Hierarchical Demand Forecasting

## Requirements

From the project spec:

1. Forecast daily units for a synthetic store-by-product retail hierarchy
   (4 stores × 6 products × 730 days, seeded, reproducible offline).
2. `config.py`: pydantic `Settings` subclass + `ForecastConfig`
   (n_days 730, n_stores 4, n_products 6, lags [1, 7, 14], n_splits 4, gap 7).
3. `data.py`: load + validate via `DatasetContract`; derive store-product
   daily series; platform DQ gates must halt the pipeline on failure.
4. `features.py`: lag + calendar features per series, **no leakage** —
   features built with `shift` only.
5. `model.py`: two models — Ridge baseline (in a sklearn `Pipeline` with
   `StandardScaler`) and `HistGradientBoostingRegressor`; global with one-hot
   series id (chosen over per-series models).
6. `evaluate.py`: honest backtest via `portfolio_core.timecv.TimeSeriesCV`;
   MAE/RMSE/MAPE via `portfolio_eval.ml.regression_metrics`; per-model
   `RunResult`; three plotly figures (forecast vs actual on example series,
   per-model metric bars, CV fold stability); report + metrics.json.
7. `cli.py`: typer commands `prepare`, `features`, `train`, `evaluate`, `all`.
8. Tests offline, runtime in seconds.

## Options considered

### A. Per-series models vs one global model with series id

- **Per-series (24 independent models)**: simple to reason about, but 24
  artefacts to version and deploy, weak transfer across series (each sees only
  730 rows), and new series require a cold-start refit.
- **Global with one-hot series id**: one artefact, the model learns
  series-level offsets plus shared seasonality/trend effects, new series are
  scored gracefully via `handle_unknown="ignore"`.
- **Global with target encoding / embeddings**: overkill for 24 series and
  leaks without careful out-of-fold encoding.

**Decision: global with one-hot series id.** Matches the spec; the panel has
identical calendars across series so a single expanding window applies to all.

### B. Validation protocol

- **Random k-fold**: rejected — masks drift; with trend + seasonality it
  leaks near-duplicate adjacent days across the split.
- **Last-block holdout**: better, but a single block gives one (possibly
  lucky) reading and no stability signal.
- **Expanding-window time CV with embargo gap** (`TimeSeriesCV`, 4 folds,
  gap 7): property-tested platform primitive; several honest readings; the
  per-fold spread doubles as a drift detector.

**Decision: expanding-window time CV, gap 7 days**, folds computed on dates
and mapped to rows so no date block straddles train/validation.

### C. Lag features vs rolling statistics

- Lags `[1, 7, 14]` capture momentum, same-weekday and two-week effects;
  weekly seasonality is also directly encoded via calendar features.
- Rolling means would add signal but complicate the leakage story (window
  must end at t−1); the spec fixes the lag set, so the simplest correct
  implementation was chosen.

**Decision: spec lags with `shift`, undefined rows dropped** (never imputed —
an imputed lag would teach the model that history is sometimes fake).

### D. Data: synthetic vs real (UCI Online Retail II)

- Real track: invoice-line data requires parsing, returns/cancellations
  handling, and a non-trivial aggregation to (date, store, product) units —
  plus network access for download. Valuable but out of scope for a
  seconds-fast, offline-guaranteed showcase.
- Synthetic: seeded, byte-identical across machines, exercises the full
  contract/DQ machinery via `synthetic://` source identity.

**Decision: both tracks.** Synthetic remains the default (CI offline, seedable);
the UCI track is implemented behind `--data-source uci` (`uci.py`): checksum-
pinned download, dependency-free XLSX streaming (stdlib zipfile/iterparse —
no openpyxl in the venv), top-8 countries × top-200 products, sales lines only
(returns excluded, documented), zero-filled daily reindex. Swapping tracks
changes nothing downstream. Full MinT covariance projection stays deferred —
the UCI panel has a flat product key, so the hierarchy is still only
store → product.

### E. Hyperparameter optimisation (wave 3)

- **Grid search**: simple and reproducible, but scales poorly beyond 2–3
  dimensions and cannot prune bad regions early.
- **Optuna TPE with median pruning**: Bayesian search over the 6-dimensional
  HGB space, with per-fold intermediate reports so unpromising trials stop
  after ~2 of 4 folds. Seeded sampler → deterministic search trajectory.

**Decision: Optuna (TPESampler seed=42, MedianPruner, ~50 trials)** with the
objective = mean MAE over the *same* date-aligned folds as the backtest
(shared `cv_row_folds`), so selection and final judgement use one protocol.
Best params are persisted to `data/hpo_best.json` and mirrored into
`ForecastConfig.hgb_tuned` defaults + `params.yaml` (production config). The
`hpo` stage is deliberately **not** part of `cli all` (minutes, not seconds).

### F. Neural model: what architecture, and what for

- Per-series embeddings + MLP over the same lag/calendar features: reuses the
  leakage-safe feature frame, trains in seconds on CPU, and plugs into the
  identical backtest via a sklearn-style `fit/predict` wrapper.
- A sequence model (LSTM/Transformer over raw windows) would need a different
  data pipeline and longer training; deferred until the simple NN justifies it.

**Decision: embedding + MLP (temporal.py)** with a hand-written loop (Adam,
grad clip 1.0, early stop on a time-ordered inner validation slice, full
seeded determinism). Honest verdict from the backtest: it lands near the
linear baseline and behind HGB — reported as-is (tree ensembles dominate on
small tabular lag problems; a sequence model is the roadmap answer).

### G. Hierarchical reconciliation

- Full MinT (covariance-based projection) is statistically heavier and needs
  residual covariance estimation across 24 series — overkill for a showcase.
  After wave 7 this stands: the UCI track's product key is flat (no category
  tree), so the hierarchy remains store → product; full covariance projection
  moves to the roadmap, gated on introducing a product-category hierarchy.
- **MinT-lite**: bottom-up store aggregation, direct store-level model, then a
  scalar shrinkage `w` distributing the parent-child discrepancy across
  children. `w` is grid-estimated on the embargoed previous fold by
  minimizing reconciled store-level MAE (a precision-ratio variant is kept
  for comparison). Coherence after reconciliation is exactly `(1-w)` times
  the incoherence before (property-tested).

## Pipeline

```mermaid
flowchart LR
    A[retail_hierarchy<br/>seed=42] --> B[DQ gates<br/>DQReport]
    B --> C[panel.parquet<br/>17,520 rows]
    C --> D[features<br/>shift lags 1/7/14 + calendar]
    D --> E[features.parquet<br/>17,184 rows]
    E --> HPO[Optuna HPO<br/>50 trials, seeded] --> CFG[hgb_tuned<br/>production params]
    E --> F[train<br/>6 models incl. temporal_net]
    CFG --> F
    F --> G[models.pkl]
    E --> H[evaluate<br/>TimeSeriesCV 4 folds, gap 7]
    G --> H
    H --> I[metrics.json<br/>report.html<br/>figures html+json]
    H --> REC[reconcile<br/>MinT-lite store level]
    REC --> I
```

## Leakage-control invariants (tested)

1. `lag_k(t) == units(t−k)` exactly — unit-tested on hand-built series.
2. CV folds: `max(train_idx) < min(val_idx)` and `val_start − train_end == gap`
   — property of `TimeSeriesCV`, re-asserted in integration tests.
3. Backtest row masks are date-aligned: newest training date < earliest
   validation date.
4. Metrics are computed on pooled **out-of-fold** predictions only.

## Changelog

- **0.4.0 (2026-10-13)** — wave 7 (roadmap delivery): UCI Online Retail II
  real-data track implemented (`uci.py`, `--data-source uci`, checksum-pinned,
  stdlib XLSX parser; 525,461 transactions → 405,416-row daily panel, 8
  countries × 200 products, 374 days, 89% zero share); probabilistic forecasts
  (`probabilistic.py`: quantile HGB p10/p50/p90 + split-conformal, empirical
  coverage vs 80% target, band figure). Real run — synthetic ladder topped by
  hgb_tuned (MAE 8.529, coverage 0.727 quantile / 0.757 conformal); UCI ladder
  topped by hgb_tuned (MAE 8.989) with ridge collapsing behind the naives
  (16.734) and persistence MAPE exploding (356%); UCI reconciliation w=0.65
  (incoherence 400.4 → 140.2); UCI conformal degenerate (q80 = 0, coverage
  0.858). Full MinT deferred (flat product key). Roadmap: per-series conformal
  / zero-inflated intervals, returns-aware demand, category hierarchy.
- **0.3.0 (2026-10-12)** — wave 3 (production depth): seeded Optuna HPO
  (`hpo.py`, TPESampler seed 42 + MedianPruner, resumable SQLite storage,
  per-trial checkpointing; 56 complete trials) over 6 HGB hyperparameters with
  the backtest's own CV folds as objective; production config `hgb_tuned`
  persisted to `data/hpo_best.json` + `params.yaml` + `HGBTunedConfig`
  defaults. Hand-written PyTorch `temporal_net` (`temporal.py`: series
  embeddings + MLP, Adam/grad-clip/early-stop loop, fully seeded) through the
  identical backtest. MinT-lite hierarchical reconciliation (`reconcile.py`:
  store-level aggregation, grid-estimated scalar shrinkage on the embargoed
  previous fold, exact coherence property). Custom figures: `hpo_history`,
  `hpo_importance`, `reconciliation_coherence`, takeaway subtitle on
  `forecast_vs_actual`. Real run (seed 42): ladder naive_mean 31.762 /
  naive_last 14.476 / ridge 9.116 / hgb 8.619 / **hgb_tuned 8.529** /
  temporal_net 9.341 MAE; hgb_tuned improves on hgb in every fold;
  reconciliation w=0.05, store MAE 23.892 → 23.837, incoherence 24.125 →
  22.919. Known platform note: HGB's OpenMP reductions make results bitwise
  stable only within fixed thread conditions; quoted numbers come from one
  canonical run.
- **0.2.0 (2026-10-12)** — wave 2: added `naive_mean` (global train mean) and
  `naive_last` (per-series persistence) baselines through the same backtest;
  `forecast_vs_actual` now overlays the best model vs the strongest naive;
  added EDA figures (`eda_series_overview`, `eda_units_distribution`); authored
  `story.yaml` (8 canonical sections). Real run (seed 42): hgb MAE 8.619 /
  MAPE 11.43%, −40.5% MAE vs naive_last (14.476); ridge −37.0%; naive_mean
  floor 31.762.
- **0.1.0 (2026-10-12)** — initial implementation: synthetic panel + DQ gates
  + dataset contract; shift-only lag/calendar features; global one-hot
  Ridge/HGB models; expanding-window backtest (4 folds, gap 7) with
  MAE/RMSE/MAPE, fold-stability and forecast-vs-actual figures; typer CLI +
  dvc stages; 25 offline tests. Real run (seed 42): ridge MAE 9.116 /
  MAPE 12.44%, hgb MAE 8.619 / MAPE 11.43%; pipeline ≈ 19 s.
