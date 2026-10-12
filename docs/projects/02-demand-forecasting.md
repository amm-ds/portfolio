# 02 · Hierarchical Demand Forecasting

**Domain:** time-series forecasting · **Data:** seeded synthetic retail
hierarchy (4 stores × 6 products × 730 days) · **Status:** working showcase on
the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

## What it shows

Leakage-safe forecasting on a store-by-product hierarchy: lag features built
with `shift` (never the current row), calendar features, and one global model
per algorithm with one-hot series identity — a Ridge baseline in a scaled
`sklearn.Pipeline` vs `HistGradientBoostingRegressor`. Honest evaluation with
the platform's embargoed expanding-window `TimeSeriesCV` (4 folds, 7-day gap),
with per-fold stability reported next to the headline metrics.

## Key results (seed 42, pooled out-of-fold over 24 series × 4 folds)

| model | MAE (units) | RMSE (units) | MAPE (%) |
|---|---|---|---|
| ridge (baseline) | 9.116 | 12.705 | 12.44 |
| **hgb** | **8.619** | **12.178** | **11.43** |

Per-fold MAE (drift visible on the last fold, as the injected trend lifts demand):

| fold | ridge | hgb |
|---|---|---|
| 1 | 9.280 | 7.860 |
| 2 | 8.572 | 8.149 |
| 3 | 8.907 | 8.916 |
| 4 | 9.705 | 9.549 |

- 6/6 DQ gates (`DQReport`) pass before any model trains; dataset carries a
  versioned `DatasetContract` with SHA-256.
- Full pipeline (`cli all`) runs in ~19 s offline; 25 tests, no network.

## Artifacts

- Figures: `reports/figures/forecast_vs_actual`, `metrics_bars`,
  `fold_stability` (`.html` + `.json` for the showcase app)
- Metrics: `reports/metrics.json` · Report: `reports/report.html`
- Dataset identity card: `data/dataset.json` · Fitted models: `data/models.pkl`

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/README.md) — problem,
  design summary, real numbers, reproduce commands, client takeaways, roadmap
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/DESIGN.md) — requirements,
  options considered (per-series vs global, validation protocol, real vs
  synthetic data), pipeline diagram, changelog
- Source: `projects/02-demand-forecasting/src/demand_forecasting/`
