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

## Key results (seed 42, pooled out-of-fold over 24 series × 4 folds)

| run | MAE (units) | RMSE (units) | MAPE (%) | Δ MAE vs naive_last |
|---|---|---|---|---|
| naive_mean (floor) | 31.762 | 42.543 | 49.02 | — |
| naive_last (persistence) | 14.476 | 19.881 | 19.28 | — |
| ridge (baseline) | 9.116 | 12.705 | 12.44 | -37.0% |
| hgb (default) | 8.619 | 12.178 | 11.43 | -40.5% |
| **hgb_tuned (Optuna, 56 trials)** | **8.529** | **12.071** | **11.34** | **-41.1%** |
| temporal_net (PyTorch) | 9.341 | 12.756 | 13.41 | -35.5% |

- HPO improved on hgb in **every** fold (e.g. fold 1: 7.860 → 7.728); the NN
  trails even the linear baseline — reported honestly.
- Reconciliation (last fold, store level): w=0.05, store MAE 23.892 → 23.837,
  incoherence 24.125 → 22.919 (exactly ×(1−w), property-tested).
- 6/6 DQ gates (`DQReport`) pass before any model trains; dataset carries a
  versioned `DatasetContract` with SHA-256.
- Full pipeline (`cli all`) ≈ 1 min unloaded; 39 offline tests.

## Artifacts

- Figures: `eda_series_overview`, `eda_units_distribution`,
  `forecast_vs_actual`, `metrics_bars`, `fold_stability`, `hpo_history`,
  `hpo_importance`, `reconciliation_coherence` (`.html` + `.json`)
- Metrics: `reports/metrics.json` · Report: `reports/report.html` ·
  Reconciliation: `reports/reconciliation.json`
- Dataset identity card: `data/dataset.json` · Fitted models: `data/models.pkl`
  · HPO: `data/hpo_best.json` (+ `hpo_study.db`) · Story: `story.yaml`

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/README.md) — problem,
  design summary, real numbers, reproduce commands, client takeaways, roadmap
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/DESIGN.md) — requirements,
  options considered (global vs per-series, validation protocol, HPO, NN,
  reconciliation), pipeline diagram, changelog
- Source: `projects/02-demand-forecasting/src/demand_forecasting/`
