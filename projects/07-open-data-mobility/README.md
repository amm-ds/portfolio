# 07 — Urban Mobility Demand Intelligence

Open-data flagship of the portfolio: end-to-end demand nowcasting on **41.2
million real NYC yellow-taxi trips** (2024, NYC TLC) joined with **NOAA
GHCN-Daily weather** (Central Park), engineered for laptop-scale memory via
lazy/streaming Polars and honest temporal validation.

- **Problem:** predict next-hour taxi pickup demand for every NYC taxi zone,
  quantify uncertainty (p90 bands), and measure how weather moves demand.
- **Grain:** one row per (zone × hour) — 265 zones × 8,784 hours = 2,327,760
  curated rows, zero-filled where a zone had no pickups.
- **Horizon:** next hour (t → t+1h). Everything on a feature row precedes the
  prediction instant — no leakage.

## Results (temporal holdout: October–December 2024, 584,855 zone-hours)

Overall test metrics (pickups/hour; lower is better):

| model | MAE | RMSE | MAPE |
|---|---|---|---|
| GBM mean (HistGradientBoosting) | **4.667** | **15.096** | 62.0% |
| TemporalNet (torch MLP, log1p target) | 5.510 | 19.686 | **54.5%** |
| naive persistence (lag-24) | 6.517 | 23.367 | 89.4% |

- The GBM wins on MAE/RMSE; the NN wins on MAPE (relative error on busy
  zones) after a log1p target transform — documented in DESIGN.md.
- **p90 uncertainty band calibration: 91.1%** of realised zone-hours fall at
  or below the quantile-GBM upper band (target 90%) — usable for fleet and
  staffing buffers.

Per-borough test MAE (GBM): Manhattan 14.2, Unknown 4.5, Queens 2.2,
Brooklyn 1.2, N/A 0.9, Bronx 0.5, EWR 0.3, Staten Island 0.2 pickups/hour.
Manhattan dominates absolute error because it dominates volume (≈60 pickups/h
per zone at peak); relative error there is comparable to other boroughs.

Weather elasticity (mean hourly pickups, rain ≥1 mm vs dry, test window):

- Outer areas drop most in rain: `Unknown`/N/A zones ≈ 0.90×, Queens 0.92×,
  Staten Island 0.93×.
- Manhattan is resilient (0.97×) — dense transit/walking alternatives keep
  curb demand stable; Bronx (1.03×) and EWR (1.08×) *rise*, consistent with
  airporter substitution to taxis.
- Caveat: raw groupby ratios, hour-of-week mix not normalised — directional,
  not causal.

Figures (interactive HTML + showcase JSON) in `reports/figures/`:
`zone_hour_heatmap` (top-30 zones × hour-of-week), `actual_vs_pred_top5`,
`borough_mae`, `weather_elasticity`, `p90_band`, `gbm_vs_nn`. Full report:
`reports/report.html`; metrics: `reports/metrics.json`.

## Design

See [DESIGN.md](DESIGN.md) for requirements, scale decisions (lazy Polars +
streaming engine, month-by-month processing, <8 GB RAM budget — observed
pipeline peak ≈ 1.8 GB), the complete zone×hour grid reindex, temporal-split
discipline (TimeSeriesCV with 24 h embargo for NN early stopping), and the
pipeline diagram.

## Reproduce

```bash
cd projects/07-open-data-mobility
uv run python -m mobility.cli all      # download → validate → join → features → train → evaluate
# or stage by stage:
uv run python -m mobility.cli download|validate|join|features|train-baselines|train-nn|evaluate
uv run python -m mobility.cli dq-report   # print/persist the latest DQ digest
```

DVC equivalent: `dvc repro` (stages mirror the CLI in `dvc.yaml`,
`params.yaml` mirrors `MobilityConfig`). Tests need no network:

```bash
uv run pytest . -q
```

First run downloads ~1.5 GB (12 monthly Parquet files + zone lookup + NOAA;
checksum-pinned in `data/raw/checksums.json`, verified loudly on every run).

## What this demonstrates for a client

- **Messy public data tamed at scale:** 41M rows gated by per-month DQ
  contracts (null-rate ceilings, range checks, freshness, row-count floors)
  that halt the pipeline loudly instead of silently shipping bad data.
- **Memory discipline:** never materialises raw trips; streaming aggregation
  to the target grain keeps peak RAM under ~2 GB on 41M rows.
- **Leakage-proof validation:** pure temporal split plus embargoed
  expanding-window CV — metrics you can trust on drifting data.
- **Decision-grade uncertainty:** calibrated p90 bands and directional
  weather elasticity, with honest caveats about causal limits.
