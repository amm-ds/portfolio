# 02 · Hierarchical Demand Forecasting

**Domain:** time-series forecasting · **Data:** UCI Online Retail II (primary
real track; seeded synthetic hierarchy as the labelled CI fast path) ·
**Status:** working showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

> A retailer stocking 200 products across 8 countries needs daily unit
> forecasts it can trust for replenishment — every point of error is working
> capital or lost sales. On real transactions, under a frozen holdout
> protocol (champion selected on origins 1..n-1, final quarter scored once),
> the champion runs at **0.843 relative MAE of the seasonal-naive floor**
> (9.545 vs 11.323 MAE; MASE 1.078 vs the naive's own 1.310 — the MASE scale
> is the naive's in-sample error from a quieter period, so 1.0 is not parity
> on this window); no run dips below MASE 1.0 there — stated, not smoothed over.
>
> [Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting)

## What it shows

Leakage-safe, production-depth forecasting on a store-by-product hierarchy: lag
features built with `shift` (never the current row), calendar features, and
global models with one-hot series identity — naive floors, seasonal-naive and
per-series ETS statistical baselines, a Ridge baseline, default + Optuna-tuned
gradient boosting (sklearn HGB, XGBoost, LightGBM arms), and a hand-written
PyTorch embedding+MLP, all through the identical embargoed expanding-window
`TimeSeriesCV` (4 folds, 7-day purge gap). Seeded Optuna HPO (resumable,
checkpointed), MinT-lite hierarchical reconciliation with a tested coherence
guarantee, and probabilistic 80% bands.

## Key results (frozen holdout: test window scored once)

Real-data track — UCI Online Retail II (top 8 countries × top 200 products,
374 days, 405,416 panel rows, 89% zero share; MAE/MASE lead, MAPE reported but
not decision-grade at this zero share). The table is scored on the final
rolling-origin window (2010-10-01..2010-12-09, the holiday quarter); the
champion was selected on origins 1..3 only and every run is scored exactly
once on the test window. *How to read: lower is better everywhere; MASE
divides by the seasonal-naive's in-sample error (fit on a quieter period —
the naive itself scores 1.310 on this window, so 1.0 is not parity here);
read Δ MASE vs sn for parity with "same day last week"; bold = selected
champion.*

| run | MAE | RMSE | MAPE | MASE | Δ MAE vs sn | Δ MASE vs sn |
|---|---|---|---|---|---|---|
| naive_mean (floor) | 12.475 | 74.699 | 90.3% | 1.382 | +1.152 | +0.072 |
| naive_last (persistence) | 11.505 | 99.548 | 327.6% | 1.331 | +0.182 | +0.021 |
| seasonal_naive (lag-7) | 11.323 | 114.921 | 305.4% | 1.310 | 0.000 | 0.000 |
| ETS (Holt-Winters, damped+weekly) | 11.471 | 80.827 | 302.7% | 1.338 | +0.148 | +0.028 |
| ridge | 12.384 | 72.680 | 221.7% | 1.395 | +1.061 | +0.085 |
| hgb (default sklearn) | 9.565 | 71.700 | 260.3% | 1.085 | −1.758 | −0.225 |
| **hgb_tuned (Optuna, 56 trials) ← best** | **9.545** | **71.847** | **230.0%** | **1.078** | **−1.778** | **−0.232** |
| xgb_tuned (Optuna, 25 trials) | 9.804 | 73.287 | 277.2% | 1.118 | −1.519 | −0.192 |
| lgbm_tuned (Optuna, 25 trials) | 9.409 | 71.360 | 272.3% | 1.076 | −1.914 | −0.234 |
| temporal_net (PyTorch emb+MLP) | 11.770 | 71.849 | 183.6% | 1.305 | +0.447 | −0.005 |

*Δ vs seasonal_naive (sn) per row — negative means the run beats "same day
last week" on that metric; the best row is marked ← best.*

![The tuned HGB run tracks two representative UCI series day by day and clears the seasonal-naive floor on the test window](../assets/projects/02-demand-forecasting/forecast_vs_actual.png){ width="100%" }

Synthetic track — seeded CI fast path (24 series × 4 origins, seed 42; note
what clean data does to the statistical baselines). Same frozen protocol: bars
are test-window numbers, champion selected on origins 1..3. *How to read: same
metrics on clean seeded data; bold = track champion (ETS overall; temporal_net
edges the ML pack on this window by 0.1 units — fold-noise level).*

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_mean (floor) | 35.946 | 48.639 | 48.26% | 3.755 |
| naive_last (persistence) | 16.223 | 22.238 | 19.47% | 1.695 |
| seasonal_naive (lag-7) | 11.780 | 16.689 | 13.98% | 1.231 |
| **ETS (Holt-Winters, damped+weekly)** | **8.924** | **12.691** | 10.37% | **0.932** |
| ridge | 9.705 | 13.706 | 11.92% | 1.014 |
| hgb | 9.549 | 13.380 | 11.58% | 0.998 |
| hgb_tuned (Optuna, 56 trials) | 9.472 | 13.269 | 11.51% | 0.990 |
| xgb_tuned (Optuna, 25 trials) | 9.525 | 13.372 | 11.59% | 0.995 |
| lgbm_tuned (Optuna, 25 trials) | 9.341 | 13.101 | 11.31% | 0.976 |
| temporal_net (PyTorch emb+MLP) | 9.244 | 12.908 | 11.38% | 0.966 |

- **Cross-track rankings reversed under the frozen protocol — in both
  directions**: the old pooled ladder claimed the best synthetic ML run
  ranked fourth on real data; on the one-shot test window
  `lgbm_tuned` posts the best MAE of all runs (9.409, ahead of the selection
  champion 9.545 — a 1.4% gap inside fold noise), while the synthetic overall
  champion `ets` ranks 6th on UCI (11.471). Configs tuned on clean synthetic
  demand behave differently on intermittent real demand; neither pooled nor
  single-window rankings should be read as more than what they are.
- ETS wins the synthetic test window outright (MASE 0.932) and loses to its
  own seasonal naive on UCI (11.471 vs 11.323, MASE 1.338) — 89% zeros break
  the smooth-seasonality assumption. Both verdicts reported.
- HPO improved on hgb in **every** fold on synthetic (8.619 → 8.529, −1.0%
  pooled legacy); on the synthetic test window the NN edges every ML run
  (9.244) without threatening ETS — reported, not hidden.
- Probabilistic 80% band, coverage AND width on the test window: quantile
  band 0.727 synthetic / 0.919 UCI (pooled); zero-aware split-conformal
  horizon set **0.741 synthetic (avg width 26.5 units, under-covers) / 0.861
  UCI (avg width 0.00 — degenerate)** against the 0.80 target. On UCI the
  champion's median forecast is 0 on ~100% of rows, so the band collapses to
  the point forecast — the honest limit, stated on the figure, whose buttons
  drop the band interactively.
- UCI reconciliation: w=0.60, incoherence 500.0 → 200.0 (coherence property
  exact); store MAE 738.7 → 676.4. Synthetic: w=0.00, accuracy effect null
  and reported as such.
- 6/6 DQ gates on both tracks; synthetic evaluate ≈ 1.5 min, UCI ≈ 7 min;
  78 offline tests.

![Bars are final-holdout-window numbers — left: MAE and RMSE per run in units; right: MASE per run, where the 1.0 gridline is not seasonal-naive parity: the MASE scale is the naive's in-sample error from a quieter period, so the seasonal-naive itself lands at 1.310 on this window. MAPE is omitted as unit-incompatible and zero-inflated (it stays in the table above)](../assets/projects/02-demand-forecasting/metrics_bars.png){ width="100%" }

## Artifacts

- Figures: interactive versions live in the [showcase app case study](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting);
  static artifacts (`.html` + `.json`, per track) in `reports/figures/` and `reports_uci/figures/`
- Metrics: `reports/metrics.json` (+ `_uci`, with `_meta` protocol block and
  `legacy_pooled_*`) · Protocol: `evaluation_metadata.json` · Report:
  `report.html` · Reconciliation: `reconciliation.json` · Probabilistic:
  `probabilistic.json` (per-horizon coverage/width + verdict) ·
  Data-generating process: `dataset_metadata.json` (UCI)
- Dataset cards: `data/dataset.json`, `data_uci/dataset.json` · HPO:
  `data/hpo_best.json` (+ `hpo_study.db`) · Story: `story.yaml`

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/README.md) — problem,
  design summary, real numbers, reproduce commands, client takeaways, roadmap
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/DESIGN.md) — requirements,
  options considered (global vs per-series, validation protocol, HPO, NN,
  reconciliation), pipeline diagram, changelog
- Dataset card: [UCI Online Retail II](../data-registry/uci-online-retail-ii.md)
- Drift response runbook: [drift-response.md](../runbooks/drift-response.md)
- Source: `projects/02-demand-forecasting/src/demand_forecasting/`
