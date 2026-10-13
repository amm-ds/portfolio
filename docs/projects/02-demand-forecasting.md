# 02 · Hierarchical Demand Forecasting

**Domain:** time-series forecasting · **Data:** seeded synthetic retail
hierarchy (4 stores × 6 products × 730 days) · **Status:** working showcase on
the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

## What it shows

Leakage-safe, production-depth forecasting on a store-by-product hierarchy: lag
features built with `shift` (never the current row), calendar features, and
global models with one-hot series identity — naive floors, a Ridge baseline,
default + Optuna-tuned gradient boosting, and a hand-written PyTorch
embedding+MLP, all through the identical embargoed expanding-window
`TimeSeriesCV` (4 folds, 7-day gap). Wave 3 adds seeded Optuna HPO (resumable,
checkpointed), MinT-lite hierarchical reconciliation with a tested coherence
guarantee, and takeaway-annotated figures.

## Key results (seed 42, pooled out-of-fold)

Synthetic track (24 series × 4 folds):

| run | MAE | RMSE | MAPE |
|---|---|---|---|
| naive_mean (floor) | 31.762 | 42.543 | 49.02% |
| naive_last | 14.476 | 19.881 | 19.28% |
| ridge | 9.116 | 12.705 | 12.44% |
| hgb | 8.619 | 12.178 | 11.43% |
| **hgb_tuned (Optuna, 56 trials)** | **8.529** | **12.071** | **11.34%** |
| temporal_net (PyTorch) | 9.341 | 12.756 | 13.41% |

Real-data track (UCI Online Retail II, 1,084 series × 4 folds, 89% zero share):

| run | MAE | RMSE | MAPE |
|---|---|---|---|
| naive_mean | 10.838 | 97.607 | 91.3% |
| naive_last | 10.288 | 135.674 | 356.2% |
| ridge (collapses) | 16.734 | 98.531 | 236.2% |
| hgb | 9.085 | 97.256 | 245.9% |
| **hgb_tuned** | **8.989** | **96.688** | 228.6% |
| temporal_net | 12.704 | 96.813 | 215.8% |

- HPO improved on hgb in **every** fold on synthetic; the NN trails the linear
  baseline on both tracks — reported honestly.
- Probabilistic 80% band coverage: synthetic 0.727 (quantile) / 0.757
  (conformal); UCI 0.919 / 0.858 with a degenerate q80 = 0 calibration —
  per-series conformal is the roadmap fix.
- UCI reconciliation: w=0.65, incoherence 400.4 → 140.2 (coherence property
  exact); store MAE 748.2 → 726.4.
- 6/6 DQ gates on both tracks; synthetic pipeline ≈ 2.5 min, UCI ≈ 5.5 min;
  46 offline tests.

## Artifacts

- Figures per track: `reports/figures/` and `reports_uci/figures/` —
  `eda_series_overview`, `eda_units_distribution`, `forecast_vs_actual`,
  `metrics_bars`, `fold_stability`, `hpo_history`, `hpo_importance`,
  `reconciliation_coherence`, `probabilistic_band` (`.html` + `.json`)
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
- Source: `projects/02-demand-forecasting/src/demand_forecasting/`
