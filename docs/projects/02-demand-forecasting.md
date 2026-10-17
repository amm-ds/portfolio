# 02 · Hierarchical Demand Forecasting

**Domain:** time-series forecasting · **Data:** UCI Online Retail II (primary
real track; seeded synthetic hierarchy as the labelled CI fast path) ·
**Status:** working showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

> A retailer stocking 200 products across 8 countries needs daily unit
> forecasts it can trust for replenishment — every point of error is working
> capital or lost sales. On real transactions the tuned gradient-boosting
> model beats the strongest naive floor (seasonal naive) by 8.8% MAE
> (8.989 vs 9.859), the only run with MASE < 1.
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
guarantee, probabilistic 80% bands, and takeaway-annotated figures.

## Key results (pooled out-of-fold)

Real-data track — UCI Online Retail II (top 8 countries × top 200 products,
374 days, 405,416 panel rows, 89% zero share; MAE/MASE lead, MAPE reported but
not decision-grade at this zero share). *How to read: lower is better everywhere;
MASE below 1.0 means the run beats "same day last week"; bold = shipped champion.*

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_mean (floor) | 10.838 | 97.607 | 91.3% | 1.132 |
| naive_last (persistence) | 10.288 | 135.674 | 356.2% | 1.168 |
| seasonal_naive (lag-7) | 9.859 | 135.298 | 439.0% | 1.117 |
| ETS (Holt-Winters, damped+weekly) | 11.256 | 116.865 | 352.3% | 1.361 |
| ridge (collapses) | 16.734 | 98.531 | 236.2% | 1.560 |
| hgb (default sklearn) | 9.085 | 97.256 | 245.9% | 1.002 |
| **hgb_tuned (Optuna, 56 trials)** | **8.989** | **96.688** | 228.6% | **0.980** |
| xgb_tuned (Optuna, 25 trials) | 9.385 | 98.136 | 275.2% | 1.042 |
| lgbm_tuned (Optuna, 25 trials) | 9.600 | 96.535 | 287.9% | 1.055 |
| temporal_net (PyTorch emb+MLP) | 12.704 | 96.813 | 215.8% | 1.232 |

Synthetic track — seeded CI fast path (24 series × 4 folds, seed 42; note what
clean data does to the statistical baselines). *How to read: same metrics on clean
seeded data; bold = track winners (ETS overall, lgbm_tuned best among ML runs).*

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_mean (floor) | 31.762 | 42.543 | 49.02% | 3.490 |
| naive_last (persistence) | 14.476 | 19.881 | 19.28% | 1.591 |
| seasonal_naive (lag-7) | 10.387 | 14.741 | 13.78% | 1.141 |
| **ETS (Holt-Winters, damped+weekly)** | **8.110** | **11.510** | 10.45% | **0.891** |
| ridge | 9.116 | 12.705 | 12.44% | 1.002 |
| hgb | 8.619 | 12.178 | 11.43% | 0.947 |
| hgb_tuned (Optuna, 56 trials) | 8.529 | 12.071 | 11.34% | 0.937 |
| xgb_tuned (Optuna, 25 trials) | 8.539 | 12.086 | 11.32% | 0.938 |
| **lgbm_tuned (Optuna, 25 trials)** | **8.413** | **11.905** | 11.16% | **0.924** |
| temporal_net (PyTorch emb+MLP) | 9.341 | 12.756 | 13.41% | 1.026 |

- **Cross-track transfer is the honest punchline**: `lgbm_tuned`, best ML run
  on synthetic (MAE 8.413, −41.9% vs persistence), drops to fourth on UCI
  (9.600); `hgb_tuned` generalises best on real data (8.989, the only run with
  MASE < 1). Configs tuned on clean synthetic demand do not transfer to
  intermittent real demand.
- ETS wins the synthetic ladder outright (MASE 0.891) and loses to its own
  seasonal naive on UCI (11.256 vs 9.859, MASE 1.361) — 89% zeros break the
  smooth-seasonality assumption. Both verdicts reported.
- HPO improved on hgb in **every** fold on synthetic (8.619 → 8.529, −1.0%);
  the NN trails the linear baseline on both tracks — reported, not hidden.
- Probabilistic 80% band coverage: synthetic 0.727 (quantile) / 0.757
  (conformal); UCI 0.919 / 0.858 with a degenerate q80 = 0 calibration —
  per-series conformal is the roadmap fix.
- UCI reconciliation: w=0.70, incoherence 384.0 → 115.2 (coherence property
  exact); store MAE 746.9 → 737.9. Synthetic: w=0.05, accuracy effect near
  null and reported as such.
- 6/6 DQ gates on both tracks; synthetic pipeline ≈ 4 min, UCI ≈ 25 min;
  58 offline tests.

## Artifacts

- Figures: interactive versions live in the [showcase app case study](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting);
  static artifacts (`.html` + `.json`, per track) in `reports/figures/` and `reports_uci/figures/`
- Metrics: `reports/metrics.json` (+ `_uci`) · Report: `report.html` ·
  Reconciliation: `reconciliation.json` · Probabilistic: `probabilistic.json`
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
