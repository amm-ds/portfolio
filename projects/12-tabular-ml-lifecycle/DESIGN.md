# DESIGN · Tabular ML & Deep Learning Lifecycle (UCI Bike Sharing, hourly)

## Requirements

1. Real primary track: UCI Bike Sharing `hour.csv` (Capital Bikeshare,
   2011–2012, 17,379 hourly rows), sha256-pinned per the
   [dataset card](../../docs/data-registry/bike-sharing.md); seeded synthetic
   twin as the CI path so tests never touch the network.
2. Time-based split: the final 8 weeks are the frozen test window; the
   8 weeks before it are validation; everything earlier is training.
3. No target leakage: `casual`/`registered` dropped (they sum to the target),
   lags are past-only positional shifts, standardization is a fitted step.
4. A model-selection ladder, every run seeded: seasonal-naive floor, ridge,
   random forest, LightGBM with time-budgeted Optuna HPO, and a tabular MLP
   in PyTorch with a hand-written training loop (AdamW, dropout, weight
   decay, early stopping on the validation window, cyclical hour embedding).
5. Overfitting controls as first-class artifacts: per-epoch train/validation
   loss curves, learning curves, and a 2x2x2 regularization ablation.
6. Frozen-test evaluation: MAE/RMSE/MAPE for every candidate vs the floor
   with paired bootstrap CIs; residual analysis sliced by hour/season/weather.
7. Everything reproducible offline (synthetic twin), runtime in minutes.

## Options considered

| Decision | Options | Chosen | Why |
|---|---|---|---|
| Lag semantics | wall-clock reindex + interpolate; positional shifts over the observed sequence | positional shifts | the series has 165 missing hours (January 2011 outages, ~1%); interpolating the target would fabricate readings, and positional lags keep a single, testable convention — stated in the feature contract |
| Grid DQ gate | demand zero missing steps; bound the missing fraction | bound (2% budget) | a perfect-grid gate fails on the real snapshot; the budget catches real outages while accepting the known ~1% |
| Standardization | whole-frame transform before split; fitted step inside `Pipeline` | fitted step inside `Pipeline` | whole-frame transform leaks train statistics into validation/test; the fitted step is also the deployment contract |
| Feature selection | top-k by MI; MI + permutation + correlation pruning | MI (train) + permutation (ridge on validation) + correlated-pair pruning (|r| > 0.9 keeps the higher-MI member) | a single ranking ignores redundancy (temp/atemp are near-duplicates); the three lenses agree on what matters and the pruning rule is parameter-free |
| Champion selection | best on test; best on validation | best on validation | each candidate receives one test score; test never selects the champion |
| MLP loss | pure MAE (L1); Huber | Huber (delta=1, standardized-y space) | L1's constant gradient trains noisily; Huber is the standard smooth MAE surrogate; the reported metric stays MAE |
| Early stopping without ES | stop at fixed epoch; best-state restore | best-state restore | "train full length" measures the damage (ablation), the shipped model keeps the best validation epoch |
| Ablation protocol | test during training; validation-only training + post-freeze test diagnostics | validation-only training + post-freeze test diagnostics | training never reads test; evaluation refits deterministic variants after freezing and labels their test scores as diagnostics, never selectors |
| LightGBM persistence | pickle the sklearn wrapper; text `model_to_string` | pickle | house pattern (05); deterministic refits make the pickle a cache of a reproducible artifact |
| Bootstrap | hourly rows only; paired hourly + day/week blocks | paired hourly + non-overlapping day/week blocks | pairing preserves model comparison within sampled hours; intact blocks expose sensitivity to serial dependence on the same test window |

## Pipeline

```mermaid
flowchart LR
    A[UCI zip, sha256 gate<br/>or synthetic twin] --> B[DQ gates<br/>26 checks]
    B --> C[time split:<br/>train | val 8wk | test 8wk]
    C --> D[features:<br/>cyclical hour/weekday/month,<br/>calendar binaries, lags 1/24/168]
    D --> E[selection: MI + permutation<br/>+ correlated-pair pruning]
    E --> F[ladder, all seeded:<br/>naive | ridge | RF<br/>LightGBM+Optuna | PyTorch MLP]
    F -->|validation picks the champion| G[frozen test window:<br/>MAE/RMSE/MAPE + paired bootstrap]
    G --> H[report:<br/>metrics.json, figures, html+md]
```

## Evaluation protocol

- **Split:** final 8 weeks (1,344 rows) = test, one score per candidate;
  the 8 weeks before = validation (model selection, HPO objective, MLP early
  stopping, shipped ablation configuration); everything earlier = training
  (first 168 rows sacrificed to NaN lags). Training never reads test.
- **Post-freeze diagnostics:** evaluation deterministically refits all eight MLP
  ablation variants after the champion/configuration freeze and records test MAE
  as diagnostics only. These scores never select a variant.
- **Judging:** MAE primary (rentals per hour), RMSE secondary, MAPE with the
  denominator floored at 1 rental; the seasonal-naive floor (same hour last
  week) is the comparator every candidate must beat.
- **Uncertainty:** 2,000 paired hourly bootstrap resamples of the MAE delta
  (floor − champion), plus paired non-overlapping 24-hour and 168-hour block
  sensitivity on the same ordered test window. The measured hourly/day/week
  95% CIs are [52.49, 63.07], [44.21, 71.83], and [38.82, 73.41].
- **Residuals:** sliced by hour × season and hour × weather situation, plus
  residual-vs-fitted for the champion.

## Platform notes

- **Dual OpenMP runtimes (macOS):** `torch` and `lightgbm` both need
  `libomp`; if torch's copy loads first, unpickling a fitted `LGBMRegressor`
  segfaults (documented in 05's DESIGN). The package `__init__` imports
  lightgbm first, so the dyld shares one runtime; every entry (CLI, stages,
  tests) goes through it. The real-run evaluate stage then deadlocked
  anyway — but in *torch*: the default 12-thread intra-op pool blocks on the
  shared runtime during `predict` (fit was safe only because it pinned one
  thread). Fix: `MLPRegressor.predict` also pins `torch.set_num_threads(1)`;
  single-thread inference on 1,344 rows is milliseconds.
- **Determinism:** LightGBM runs `deterministic=True, force_row_wise=True,
  num_threads=1`; the MLP fits single-threaded with seeded init, seeded
  shuffling and float32 CPU ops; RF is `n_jobs=1`; Optuna uses a seeded TPE
  sampler. Same seed → same metrics (tested for ridge and MLP).

## Changelog

- 2026-11-16 · Removed all test access from training. Evaluation now labels
  ablation test scores as post-freeze diagnostics and adds paired 24-hour and
  168-hour block-bootstrap sensitivity. Champion, candidate metrics, and the
  hourly interval are unchanged; day/week 95% CIs are [44.21, 71.83] and
  [38.82, 73.41].
- 2026-11-04 · Initial implementation: prepare (sha256-pinned UCI zip +
  synthetic twin + DQ gates), EDA figures, time-split features with
  MI/permutation/correlation selection, the five-model ladder with seeded
  LightGBM HPO and the hand-written PyTorch MLP loop, frozen evaluation
  with paired bootstrap CIs, report assembly, 34 tests (91% coverage).
  Real run: validation picks the MLP (34.2 MAE) over LightGBM (34.4); test
  25.4 vs the floor's 83.2, improvement +57.8 with 95% CI [52.5, 63.1].
  Two platform fights fixed along the way: LightGBM-unpickle segfault (import
  order, package `__init__`) and a torch intra-op deadlock in `predict`
  (single-thread pinning, with a regression assertion). Random-forest depth
  capped at 32 after the unbounded fit produced a 366 MB pickle.
