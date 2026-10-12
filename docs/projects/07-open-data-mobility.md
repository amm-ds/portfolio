# Urban Mobility Demand Intelligence

**Flagship — complete.** End-to-end demand nowcasting on real, messy,
GB-scale public data: 41.2M NYC yellow-taxi trips (2024) joined with NOAA
GHCN-Daily weather, engineered with lazy/streaming Polars under a 2 GB RAM
peak, gated by per-month DQ contracts, and validated with leakage-proof
temporal splits.

## Key results (temporal holdout Oct–Dec 2024, 584,855 zone-hours)

| model | MAE | RMSE | MAPE |
|---|---|---|---|
| GBM mean | **4.67** | **15.10** | 62.0% |
| TemporalNet (torch, log1p target) | 5.51 | 19.69 | **54.5%** |
| naive lag-24 | 6.52 | 23.37 | 89.4% |

p90 quantile band calibration: **91.1%** coverage. Per-borough GBM MAE peaks
in Manhattan (14.2 pickups/h) where volume peaks. Weather elasticity:
outer-borough curb demand drops 7–10% in rain (Queens 0.92×, Staten Island
0.93×) while Manhattan holds (0.97×) and EWR rises (1.08×) — directional,
with documented caveats.

## Where things live

- Code + design: [projects/07-open-data-mobility](https://github.com/amm-ds/portfolio/tree/main/projects/07-open-data-mobility) — pipeline `mobility download|validate|join|features|train-baselines|train-nn|evaluate|dashboard|dq-report|all`, DVC stages in `dvc.yaml`
- Dataset cards: [NYC TLC](../data-registry/nyc-tlc.md) · [NOAA GHCN](../data-registry/noaa-ghcn.md)

## Data attribution

- **NYC TLC Trip Records** — NYC TLC terms of use; free, anonymous download.
  Monthly yellow-taxi Parquet, snapshot 2026-10-12, checksum-pinned.
- **NOAA GHCN-Daily** (station USW00094728, Central Park) — public domain
  (US Government work).

Both are downloaded by the pipeline itself; nothing raw is committed to git
(DVC tracks the derived data products).
