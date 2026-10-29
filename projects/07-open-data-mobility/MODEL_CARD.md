# Model Card — Urban Mobility Demand Intelligence (Project 07)

## Intended use

Next-hour yellow-taxi pickup-demand forecasts per NYC taxi zone (265 zones),
with a p90 upper uncertainty band, served at
`POST /projects/07-open-data-mobility/forecast`. Intended for operational
planning: fleet staging, driver shift timing, and staffing buffers. Horizon is
**one hour**; the model is a point forecaster + quantile band, not a
long-range planner, and not a causal model of demand.

## Data

| source | slice | license |
|---|---|---|
| NYC TLC yellow taxi trips | 2024-01…2024-12, 41.2M trips (12 monthly Parquet, checksum-pinned) | NYC TLC terms of use |
| NYC TLC green taxi trips | 2024-01…2024-03 (bounded transfer study only) | NYC TLC terms of use |
| TLC taxi-zone lookup + `taxi_zones.zip` boundaries | all 265 zones | NYC TLC terms of use |
| NOAA GHCN-Daily USW00094728 (Central Park) | daily PRCP/SNOW/TMAX/TMIN, QC flags honoured | public domain (US Gov) |

Features: per-zone lags [1, 2, 24, 168], calendar (hour, day-of-week, month),
same-day weather. Target: next-hour pickups. Train < 2024-10-01 ≤ test
(pure temporal split); HPO validation = last expanding-window fold with a
24 h embargo, train side only.

**Green-taxi transfer caveat:** yellow-trained weights do **not** transfer
cleanly to green demand (March 2024: MAE 0.296 vs persistence 0.212 — wins
RMSE/MAPE, loses MAE). Per-service retraining is required before serving any
non-yellow service class.

## Metrics (Q4 2024 holdout, 584,855 zone-hours)

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_lag24 (persistence) | 6.517 | 23.367 | 89.4% | 1.063 |
| gbm_mean | 4.667 | 15.096 | 62.0% | 0.761 |
| **gbm_tuned (served)** | 4.676 | 15.189 | 61.6% | 0.763 |
| gbm_xgb_tuned | 4.487 | 14.785 | 58.2% | 0.732 |
| gbm_lgbm_tuned | 4.582 | 14.794 | 59.9% | 0.747 |
| temporal_net | 5.510 | 19.686 | 54.5% | 0.899 |
| temporal_net_tuned | 5.178 | 21.580 | 57.5% | 0.845 |

MASE = MAE ÷ in-sample seasonal-naive-24 error (scale ≈ 6.13 pickups/hour).
Lag 24 is the same hour yesterday, not the same hour last week.

Served-model slices (gbm_tuned): per-borough test MAE — Manhattan 14.2,
Unknown 4.5, Queens 2.2, Brooklyn 1.2, N/A 0.9, Bronx 0.5, EWR 0.3,
Staten Island 0.2 pickups/hour. p90 band coverage 90.8% overall (target 90%).

## Limits

- **Thin-data zones:** sparse "N/A"/outer zones under-cover at 84.7% — the
  p90 band is too tight where data is thin; do not staff against those bands.
- **Weather is associative, not causal:** elasticity findings (rain −7–10% in
  outer boroughs) are raw groupbys without hour-of-week normalisation.
- **Per-service retraining required** for green/FHV classes (see caveat).
- **Manhattan dominates absolute error** (volume ∝ error); relative error is
  comparable across boroughs.
- **Serving selection is validation-based:** challengers that beat the served
  model on test (xgb −4.1% MAE) were not promoted because they lost on the
  embargoed validation window; switching on test results would be leakage.

## Reproduce

`uv run python -m mobility.cli all` (see README); metrics via
`uv run dvc metrics show`; serving artifact via `build-serving-artifact`.
