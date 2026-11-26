# 12 · Tabular ML & Deep Learning Lifecycle

Classical-ML + DL showcase: predict hourly bike rentals on the real **UCI
Bike Sharing** series (Capital Bikeshare, Washington D.C., 2011–2012) through
the full lifecycle — sha256-pinned ingest, DQ gates, time-based split,
leakage-safe feature engineering, seeded model selection from a seasonal-naive
floor to a hand-written PyTorch MLP, and a frozen test window with
paired bootstrap CIs.

**Status:** working showcase on the standard platform.

## Problem

How many bikes will be rented in the next hour, and how much better than
"same hour last week" can a model honestly get? The primary track is the real
UCI Bike Sharing `hour.csv` (17,379 hourly rows, behind the same DQ gates and
DatasetContract — see [data-registry/bike-sharing](../../docs/data-registry/bike-sharing.md));
a seeded synthetic twin with the same schema remains as the clearly labeled
CI path (`data_source: synthetic`) so tests never touch the network. The
split is time-based: the **final 8 weeks are the frozen test window**,
the 8 weeks before it are validation, everything earlier is training.

## Design

Everything from raw frame to metric follows one contract:

```text
raw zip ──▶ sha256 gate ──▶ hour.csv ──▶ DQ gates (26 checks)
      ──▶ time split: train | validation 8wk | frozen test 8wk
      ──▶ features: cyclical hour/weekday/month, calendar binaries,
          lags 1h/24h/168h (past-only, positional)
      ──▶ selection: MI (train) + permutation (ridge on validation)
          + correlated-pair pruning (committed run drops atemp and keeps temp, despite atemp's higher MI)
      ──▶ ladder, every run seeded:
          seasonal naive | ridge | random forest | LightGBM + Optuna HPO
          | tabular MLP (PyTorch, hand-written loop)
      ──▶ frozen test: MAE/RMSE/MAPE + paired bootstrap CIs
```

- **Leakage rules** (`data/feature_selection.json` is the contract): lags at
  time t read only counts strictly before t; validation/test lags read their
  own past, which is available at prediction time; standardization is a
  fitted step inside the sklearn Pipeline (train statistics only); the first
  168 training rows lose their NaN lag rows. `casual`/`registered` are
  dropped — they sum to the target.
- **Positional lags, stated:** the UCI series has 165 missing hours, mostly
  early 2011 plus a 36-hour gap on 2012-10-29/30 inside validation. Lags are
  positional shifts over the observed sequence, so lag 168 and the seasonal floor
  can drift up to 36 hours for about a week after that gap; lag 24 is shifted for
  about a day and a half. The DQ gate bounds the missing fraction at 2% instead
  of demanding a perfect grid.
- **The MLP is a first-class citizen, not a victory lap:** cyclical-hour
  `nn.Embedding` + numeric trunk, AdamW, dropout, weight decay, Huber loss
  (smooth MAE surrogate in standardized-y space), early stopping on the
  validation window with best-state restore, per-epoch train/validation loss
  curves, and a 2x2x2 ablation (dropout x weight decay x early stopping).
  It ships even where trees win — the loop itself is the deliverable.
- **Overfitting controls as artifacts:** `mlp_loss_curves`, `learning_curves`
  (LightGBM + MLP), and `ablation_dotplot` are committed figures.

Full rationale and rejected alternatives: [DESIGN.md](DESIGN.md).

## Results (real run: UCI Bike Sharing, 17,379 rows → 1,344-row frozen test window)

| candidate | val MAE | test MAE | test RMSE | test MAPE % |
|---|---|---|---|---|
| seasonal naive (floor) | 88.7 | 83.2 | 134.0 | 153.2 |
| ridge | 68.9 | 51.1 | 77.8 | 86.4 |
| random forest | 39.5 | 26.3 | 45.7 | 25.7 |
| LightGBM (Optuna HPO) | 34.4 | 25.4 | 40.2 | 27.4 |
| tabular MLP (PyTorch) ← validation pick, tied | 34.2 | 25.4 | 39.3 | 33.7 |

Key findings:

- **Every candidate and its one test score:** see `reports/metrics.json` and
  the `model_comparison` figure; the served model was chosen by validation
  MAE, never by test.
- **The floor is real:** the seasonal-naive comparator (same hour last week)
  posts 83.2 test MAE; the served MLP improves on it by 57.8
  rentals/hour on average. The hourly paired-bootstrap 95% CI is [52.5, 63.1];
  day-block and week-block sensitivity intervals are wider at [44.2, 71.8] and
  [38.8, 73.4], respectively (2,000 resamples each). All exclude zero.
- **Feature selection agreed with the EDA:** mutual information ranks the
  three lags first (MI 0.89 / 0.76 / 0.71 nats), then the cyclical hour pair;
  the committed correlated-pair record dropped `atemp` (r = 0.987 with `temp`)
  despite `atemp`'s slightly higher MI; correcting that mismatch needs a fresh run.
- **Read the ablation at face value:** the 2x2x2 grid is on `ablation_dotplot`.
  Early stopping is the load-bearing control (every off-row is worse on
  validation); the validation argmin is a dropout-off row about 2 rentals below
  the shipped configuration. The configuration fixed in `params.yaml` before
  the ablation stands. Variant
  test scores are post-freeze diagnostics, never selectors.
- **The MLP-trees race is a tie, not a champion:** validation MAE 34.2 (MLP)
  vs 34.4 (LightGBM); the paired bootstrap on the validation difference
  (MLP − LightGBM) is −0.18 with 95% CI [−1.7, +1.2] (2,000 seeded
  resamples, `metrics.json:validation_tie_interval`) — the interval spans
  zero, so per the stated protocol the two are tied on validation and the MLP
  stays the served artifact without a champion label. On the single test pass
  LightGBM's MAE is 0.06 rentals lower while
  the MLP holds the better RMSE (39.3 vs 40.2). Both crush the floor's 83.2.
- **The residual slices name the next feature:** high-demand hours
  under-forecast by +28.6 rentals on average, while late-December holiday hours
  and several bad-weather cells over-forecast; calendar-event features are next.
- **Limits, labeled:** validation made every choice; ablation test scores are
  post-freeze diagnostics. Day/week intervals expose serial-dependence
  sensitivity. MAPE denominators are floored at 1 rental; one city over two
  years/four seasons — transfer is plausible, not measured.

## Limits

The remaining error concentrates at rush hour and in bad weather (residual
slices), the served model is not refit on train+validation before serving, and
transfer to another city's system is unverified — both listed under Roadmap
below. Probabilistic forecasts and calendar-event features are deferred.

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
(36, no network, synthetic fixtures only):

```bash
uv run pytest projects/12-tabular-ml-lifecycle -q
```

## Common errors

| symptom | cause | fix |
|---|---|---|
| `import lightgbm` (or the LightGBM fit) fails on macOS; MLP inference mysteriously slow | the LightGBM wheel links brew's OpenMP — covered in **Prerequisites** above — and torch's default thread pool can block on the libomp it bundles (full mechanism in [DESIGN.md § Platform notes](DESIGN.md#platform-notes)) | `brew install libomp`; the thread pinning (`torch.set_num_threads(1)`, single-threaded LightGBM/RF) is already in the code — read the platform note before touching it |

## What this demonstrates for a client

- **A lifecycle, not a notebook:** pinned ingest, DQ gates as halting
  checks, a written feature-selection contract, a seeded model ladder, and a
  frozen holdout — every stage one `dvc repro` away.
- **Leakage handled structurally:** past-only lags, fitted scalers, dropped
  target-sum columns, and a test window no choice ever touches — with tests
  that mutate future rows to prove lags never look ahead.
- **Deep learning without a framework hiding the loop:** the PyTorch MLP
  carries a hand-written training loop with the overfitting controls measured,
  not assumed (loss curves, learning curves, 2x2x2 ablation).
- **Honest uncertainty:** the served-model-versus-floor gap carries paired hourly,
  day-block, and week-block intervals; residual slices say where the model is
  still wrong. Variant test scores are labeled post-freeze diagnostics.

## Roadmap

- **Delivered:** real UCI data behind sha256 + DQ gates; time split with a
  frozen test window; MI/permutation/correlation feature selection; the
  five-model seeded ladder with time-budgeted LightGBM HPO and the
  hand-written PyTorch MLP; bootstrap CIs; residual analysis.
- **Delivered:** overfitting-control artifacts (per-epoch loss curves,
  learning curves, 2x2x2 ablation) as committed figures.
- **Deferred:** calendar-event features (holidays are binary flags only) and
  probabilistic forecasts; refitting the selected model on train+validation before
  serving; transfer checks on another city's system.

## Figures

| figure | file |
|---|---|
| ablation dotplot | [reports/figures/ablation_dotplot.html](reports/figures/ablation_dotplot.html) |
| bootstrap ci | [reports/figures/bootstrap_ci.html](reports/figures/bootstrap_ci.html) |
| correlation heatmap | [reports/figures/correlation_heatmap.html](reports/figures/correlation_heatmap.html) |
| learning curves | [reports/figures/learning_curves.html](reports/figures/learning_curves.html) |
| mi lollipop | [reports/figures/mi_lollipop.html](reports/figures/mi_lollipop.html) |
| mlp loss curves | [reports/figures/mlp_loss_curves.html](reports/figures/mlp_loss_curves.html) |
| model comparison | [reports/figures/model_comparison.html](reports/figures/model_comparison.html) |
| rentals by hour season | [reports/figures/rentals_by_hour_season.html](reports/figures/rentals_by_hour_season.html) |
| residual heatmap | [reports/figures/residual_heatmap.html](reports/figures/residual_heatmap.html) |
| residual vs fitted | [reports/figures/residual_vs_fitted.html](reports/figures/residual_vs_fitted.html) |
| temp vs rentals | [reports/figures/temp_vs_rentals.html](reports/figures/temp_vs_rentals.html) |

