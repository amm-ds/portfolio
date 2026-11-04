# 12 · Tabular ML & Deep Learning Lifecycle

Classical-ML + DL showcase: predict hourly bike rentals on the real **UCI
Bike Sharing** series (Capital Bikeshare, Washington D.C., 2011–2012) through
the full lifecycle — sha256-pinned ingest, DQ gates, time-based split,
leakage-safe feature engineering, seeded model selection from a seasonal-naive
floor to a hand-written PyTorch MLP, and a scored-once test window with
paired bootstrap CIs.

**Status:** working showcase on the standard platform.

## Problem

How many bikes will be rented in the next hour, and how much better than
"same hour last week" can a model honestly get? The primary track is the real
UCI Bike Sharing `hour.csv` (17,379 hourly rows, behind the same DQ gates and
DatasetContract — see [data-registry/bike-sharing](../../docs/data-registry/bike-sharing.md));
a seeded synthetic twin with the same schema remains as the clearly labeled
CI path (`data_source: synthetic`) so tests never touch the network. The
split is time-based: the **final 8 weeks are the scored-once test window**,
the 8 weeks before it are validation, everything earlier is training.

## Design

Everything from raw frame to metric follows one contract:

```
raw zip ──▶ sha256 gate ──▶ hour.csv ──▶ DQ gates (26 checks)
      ──▶ time split: train | validation 8wk | test 8wk (scored once)
      ──▶ features: cyclical hour/weekday/month, calendar binaries,
          lags 1h/24h/168h (past-only, positional)
      ──▶ selection: MI (train) + permutation (ridge on validation)
          + correlated-pair pruning (|r| > 0.9 keeps higher-MI member)
      ──▶ ladder, every run seeded:
          seasonal naive | ridge | random forest | LightGBM + Optuna HPO
          | tabular MLP (PyTorch, hand-written loop)
      ──▶ scored-once test: MAE/RMSE/MAPE + paired bootstrap CIs
```

- **Leakage rules** (`data/feature_selection.json` is the contract): lags at
  time t read only counts strictly before t; validation/test lags read their
  own past, which is available at prediction time; standardization is a
  fitted step inside the sklearn Pipeline (train statistics only); the first
  168 training rows lose their NaN lag rows. `casual`/`registered` are
  dropped — they sum to the target.
- **Positional lags, stated:** the UCI series has 165 missing hours (the
  January 2011 outage pattern, ~1% of rows). Lags are positional shifts over
  the observed sequence, so "lag 168" is same-hour-last-week give or take the
  outage gaps — the DQ gate bounds the missing fraction at 2% instead of
  demanding a perfect grid, and this convention is written into the contract.
- **The MLP is a first-class citizen, not a victory lap:** cyclical-hour
  `nn.Embedding` + numeric trunk, AdamW, dropout, weight decay, Huber loss
  (smooth MAE surrogate in standardized-y space), early stopping on the
  validation window with best-state restore, per-epoch train/validation loss
  curves, and a 2x2x2 ablation (dropout x weight decay x early stopping).
  It ships even where trees win — the loop itself is the deliverable.
- **Overfitting controls as artifacts:** `mlp_loss_curves`, `learning_curves`
  (LightGBM + MLP), and `ablation_dotplot` are committed figures.

Full rationale and rejected alternatives: [DESIGN.md](DESIGN.md).

## Results (real run: UCI Bike Sharing, 17,379 rows → 1,344-row scored-once test window)

| candidate | val MAE | test MAE | test RMSE | test MAPE % |
|---|---|---|---|---|
| seasonal naive (floor) | 88.7 | 83.2 | 134.0 | 153.2 |
| ridge | 68.9 | 51.1 | 77.8 | 86.4 |
| random forest | 39.5 | 26.3 | 45.7 | 25.7 |
| LightGBM (Optuna HPO, 50 trials) | 34.4 | 25.4 | 40.2 | 27.4 |
| tabular MLP (PyTorch) ← champion | 34.2 | 25.4 | 39.3 | 33.7 |

Key findings:

- **Every candidate and its one test score:** see `reports/metrics.json` and
  the `model_comparison` figure; the champion was chosen by validation MAE,
  never by test.
- **The floor is real:** the seasonal-naive comparator (same hour last week)
  posts 83.2 test MAE; the champion improves on it by 57.8
  rentals/hour on average, 95% paired-bootstrap CI [52.5, 63.1] over 2,000
  resamples — CI excludes zero.
- **Feature selection agreed with the EDA:** mutual information ranks the
  three lags first (MI 0.89 / 0.76 / 0.71 nats), then the cyclical hour pair;
  the correlated-pair pruning dropped `atemp` (r = 0.987 with `temp`) — the
  heatmap's near-duplicate pair, resolved by rule rather than by hand.
- **Read the ablation at face value:** the 2x2x2 grid is on `ablation_dotplot`.
  Early stopping is the load-bearing control (every off-row is worse); the
  validation argmin is a dropout-off row ~2 rentals inside row noise, so the
  pre-registered configuration stands. The test column is evidence, never a
  selector (see limits).
- **The MLP-trees race is a dead heat:** validation picks the MLP (34.2 vs
  34.4); on the single test pass LightGBM's MAE is 0.06 rentals lower while
  the MLP holds the better RMSE (39.3 vs 40.2). Both crush the floor's 83.2.
- **The residual slices name the next feature:** `residual_heatmap` and
  `residual_vs_fitted` for the champion show where the model still
  under-forecasts (rush-hour peaks and bad weather).
- **Limits, labeled:** the test window is scored once per candidate and no
  choice used it; MAPE denominators are floored at 1 rental; one city, two
  seasons — transfer is plausible, not measured.

## Reproduce

**Prerequisites:** Python 3.12 via uv. On macOS, `brew install libomp` — the
LightGBM wheel links brew's OpenMP (same prerequisite as project 05).

```bash
cd projects/12-tabular-ml-lifecycle
uv run python -m tabular_ml_lifecycle.cli all   # prepare (UCI) → eda → features → train → evaluate → report, ~10-20 min
# CI path (no network): edit params.yaml to `data_source: synthetic`, then the same command
# or stage-wise via DVC:
dvc repro
uv run dvc metrics show                          # run ladder from the lockfile
```

Deterministic: seed 42 controls the synthetic twin, the splits, the Optuna
sampler, LightGBM (`deterministic=True, num_threads=1`), the random forest
(`n_jobs=1`) and the MLP (seeded init + shuffling, single-threaded). Tests
(34, no network, synthetic fixtures only, 91% src coverage):

```bash
uv run pytest projects/12-tabular-ml-lifecycle -q
```

## What this demonstrates for a client

- **A lifecycle, not a notebook:** pinned ingest, DQ gates as halting
  checks, a written feature-selection contract, a seeded model ladder, and a
  scored-once holdout — every stage one `dvc repro` away.
- **Leakage handled structurally:** past-only lags, fitted scalers, dropped
  target-sum columns, and a test window no choice ever touches — with tests
  that mutate future rows to prove lags never look ahead.
- **Deep learning without a framework hiding the loop:** the PyTorch MLP
  carries a hand-written training loop with the overfitting controls measured,
  not assumed (loss curves, learning curves, 2x2x2 ablation).
- **Honest uncertainty:** every candidate's test score carries paired
  bootstrap CIs against the floor; residual slices say where the model is
  still wrong.

## Roadmap

- **Delivered:** real UCI data behind sha256 + DQ gates; time split with a
  scored-once test window; MI/permutation/correlation feature selection; the
  five-model seeded ladder with time-budgeted LightGBM HPO and the
  hand-written PyTorch MLP; bootstrap CIs; residual analysis.
- **Delivered:** overfitting-control artifacts (per-epoch loss curves,
  learning curves, 2x2x2 ablation) as committed figures.
- **Deferred:** calendar-event features (holidays are binary flags only) and
  probabilistic forecasts; refitting the champion on train+validation before
  serving; transfer checks on another city's system.
