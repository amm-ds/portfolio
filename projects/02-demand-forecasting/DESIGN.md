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

### H. Final holdout + frozen selection protocol (wave 18, audit hardening)

- **Status quo (waves 1–13)**: all folds pooled into one headline number, and
  the champion pick read the same pooled numbers — selection and final
  judgement were the same data, so the headline was optimistically biased and
  the "test" was not a test.
- **Last-block holdout without rolling origins**: a single final block is
  honest but gives one (possibly lucky) reading and no stability signal.
- **Decision: rolling-origin holdout (`rolling_origin_holdout_v1`)** — the
  existing expanding-window folds stay, but the LAST origin becomes the test
  window: model/feature selection (`best_model`, champion) pools folds
  1..n-1 ONLY, every candidate is then scored exactly once on the test
  window, and the committed headline metrics are the test-window numbers.
  The pre-holdout all-fold pooled values are kept per model under
  `legacy_pooled_*` (nothing silently dropped). Property-tested: shuffling
  the test fold's actuals leaves the selection result unchanged. The
  protocol is emitted machine-readably in `evaluation_metadata.json`
  (`selection_used_origins` vs `test_origin`), and metric suite extended
  (bias, zero-safe WAPE, fold MAEs + std/range, per-horizon h=1..14 MAE/MASE
  over the test window's final 14 days). The uncertainty band is evaluated on
  the test window too: per-horizon coverage AND average width, with a
  calibrated/conservative/optimistic verdict at the 0.05 tolerance.

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
5. Frozen holdout: the last origin is the test window; selection pools
   origins 1..n-1 only — property-tested by shuffling the test fold's
   actuals and asserting the champion pick is unchanged.

## Experiment versioning (ADR-0007 worked example)

HPO search budgets are versioned as DVC experiments, not ad-hoc runs. The
mechanics (params flow through `params.yaml` — the CLI overlays it onto
`ForecastConfig`, so `--set-param` changes what actually executes):

```bash
# queue two search-budget variants of the hpo stage
uv run dvc exp run --queue --set-param hpo_n_trials=8 hpo
uv run dvc exp run --queue --set-param hpo_n_trials=12 hpo
uv run dvc exp run --run-all          # workers execute in temp workspaces
uv run dvc exp show --no-pager        # compare budgets side by side
```

Nothing from an experiment is applied to `params.yaml` automatically — the
full studies set the production configs (`data/hpo_best*.json` +
`params.yaml`); experiments only answer "would a smaller budget have found
it?".

Captured `dvc exp show --no-pager` (this checkout, trimmed):

```text
Task     Name             Created    Status
a75b2ee  train-rows-1m    03:24 AM   Failed
9b879a7  train-rows-500k  03:25 AM   Failed
```

(Only foreign queued tasks are visible: experiments are queued repo-wide.)

**Current blocker, worked-example lesson included:** every `dvc exp run` /
`dvc repro` validates the *whole repository* pipeline, and 07's dvc.yaml
currently declares `reports/models/predictions_baseline.parquet` as an output
of both `train_baselines` and `train_arms`. Until that overlap is removed,
all experiment execution repo-wide fails with:

```text
ERROR: output '../07-open-data-mobility/reports/models/predictions_baseline.parquet' is specified in:
	- ../07-open-data-mobility/dvc.yaml:train_arms
	- ../07-open-data-mobility/dvc.yaml:train_baselines
```

`dvc commit`, `dvc exp show` and `dvc metrics show` are unaffected (no
pipeline build). The queue commands above are the exact ones to re-run once
07's graph is fixed; the hpo stage is queue-ready (`params.yaml` carries
`hpo_n_trials`, the CLI overlays it).

## Changelog

- **0.7.0 (2026-10-23)** — wave 18 (senior-review hardening): frozen holdout
  protocol `rolling_origin_holdout_v1` — the last rolling-origin window is the
  test window; `best_model`/champion selection pools folds 1..n-1 only
  (property-tested: shuffling the test window's actuals leaves the pick
  unchanged); all candidates are scored once on the test window and those are
  the committed headline numbers. The pre-holdout all-fold pooled values are
  retained per model as `legacy_pooled_*` in metrics.json (the old quoted
  numbers live on there — README/story now quote only regenerated values, and
  `tests/test_readme_numbers.py` drift-guards the README tables against the
  committed metrics). `reports*/evaluation_metadata.json` states the protocol
  machine-readably (selection_used_origins vs test_origin, within-train-window
  preprocessing guarantee, metric definitions). Metric suite extended: bias,
  zero-safe WAPE, `fold_maes`/`fold_mae_std`/`fold_mae_range`, per-horizon
  (h=1..14) `horizon_mae`/`horizon_mase` over the test window's final 14 days
  (demo-payload window convention); the metrics figure keeps unit-mixing
  metrics on separate axes and carries the zero-demand MAPE caveat.
  Uncertainty evaluation on the test window: per-horizon empirical coverage
  AND average width plus a `calibration_verdict` (|coverage−target| ≤ 0.05)
  in probabilistic.json. UCI data-generating process documented in
  `reports_uci/dataset_metadata.json` (+ README/DESIGN section, emitted by
  `prepare`), including the "zero-sales days may be missing rather than true
  zero demand (no trading calendar)" caveat and the one-sentence target
  definition. Regenerated canonical run, headline moves (test window =
  holiday quarter): UCI champion still `hgb_tuned` by selection (9.545 MAE /
  1.078 MASE) but no run dips below MASE 1.0 — the seasonal-naive itself
  scores 1.310 there, its scale being in-sample error from a quieter period,
  so 1.0 is not parity on this window — and `lgbm_tuned` posts the best
  test-window MAE (9.409) — the old "synthetic champion ranks 4th on real
  data" claim was a pooled artifact and is corrected; synthetic test window
  still led by ETS (8.924), `temporal_net` best ML (9.244); reconciliation
  w=0.60 UCI (store MAE 738.7→676.4) / w=0.00 synthetic; band verdicts
  optimistic (synthetic, 0.741 @ 26.5u) and degenerate-conservative (UCI,
  0.861 @ 0.00u). dvc repro remains broken repo-wide (07 overlap) — stages
  were executed via their `cmd`s directly.
- **0.6.0 (2026-10-15)** — wave 13 (external-audit driven): UCI Online Retail
  II promoted to the headline track (README/story lead with real numbers;
  synthetic explicitly the CI fast path — and a CLI bug fixed where the
  params.yaml overlay clobbered `--data-source`). Statistical baselines:
  `seasonal_naive` (lag-7) and per-series ETS (`statsmodels>=0.14` new dep;
  damped additive Holt-Winters, fallback chain to seasonal naive for short or
  failing series, documented + tested) through the identical backtest on both
  tracks. **MASE** added to every run (per-fold in-sample seasonal-naive
  scale, pooled). Audit figures: `forecast_fan` (p10/p50/p90 + actual, real
  track), `coherence_heatmap` (per-store incoherence before/after), takeaway
  on `fold_stability`. Conformal coverage stated as h=1-only with the
  multi-horizon note persisted in `probabilistic.json`. Real run — UCI ladder:
  hgb_tuned champion (MAE 8.989, MASE 0.980, only run < 1.0), seasonal_naive
  best floor (9.859), ETS 11.256 (intermittency breaks Holt-Winters), lgbm
  synthetic champion drops to 9.600 (cross-track transfer finding), ridge
  collapses (16.734). Synthetic ladder: ETS wins outright (8.110, MASE 0.891)
  — the deliberate mirror image. Reconciliation UCI w=0.70 (incoherence
  384.0 → 115.2, store MAE 746.9 → 737.9); coverage 0.727/0.757 synthetic,
  0.919/0.858 UCI. Note: the store-level reconciliation backtest re-fits HGB
  and jitters run-to-run within the documented OpenMP-reduction tolerance —
  the wave-13-canonical rerun moved w 0.65 → 0.70 while the 10-run ladder
  stayed bitwise identical; quoted reconciliation numbers are from the latest
  canonical run.
- **0.5.0 (2026-10-15)** — wave 11 (general-purpose boosting arms): XGBoost +
  LightGBM added (`xgboost>=2.0`, `lightgbm>=4.0`); `hpo.py` generalized to
  per-arm seeded studies (hgb 56 trials, xgb 25, lgbm 25) with per-arm search
  spaces, resumable per-arm studies in one SQLite storage, and per-arm param
  persistence (`data/hpo_best_{xgb,lgbm}.json`); `cli hpo --model`;
  `params.yaml` is now overlaid onto `ForecastConfig` (dvc `--set-param`
  changes real runs). macOS: single shared libomp runtime across torch /
  xgboost / lightgbm (import-order guard in temporal.py, rpath graft in the
  venv, single-threaded torch in the NN) — dual OpenMP runtimes segfault or
  deadlock. dvc.yaml: evaluate declares `reports/metrics.json` under
  `metrics:`, figures flow through the stage's figures-dir out. Real run
  (seed 42, 8 runs): lgbm_tuned MAE 8.413 (new champion, -1.4% vs hgb_tuned
  8.529), xgb_tuned 8.539 (wash), temporal_net 9.341; reconciliation w=0.05;
  quantile coverage 0.727 / conformal 0.757. Experiment versioning section
  added; dvc exp execution blocked by 07's overlapping output (documented).

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
