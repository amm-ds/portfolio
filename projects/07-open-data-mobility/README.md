# 07 — Urban Mobility Demand Intelligence

Next-hour NYC taxi-demand forecasts by zone, built from **41.2 million real
2024 yellow-taxi trips** and NOAA GHCN-Daily weather at Central Park. Lazy and
streaming Polars keeps the pipeline within a laptop memory budget.

The curated grain is one row per zone-hour: 265 zones × 8,784 hours =
2,327,760 rows, with zero-filled demand. Every feature precedes the prediction
instant. The primary evaluation is the October–December 2024 temporal holdout.

## Reproduce

```bash
cd projects/07-open-data-mobility
uv run python -m mobility.cli all      # download → validate → join → features → train → evaluate

# individual stages
uv run python -m mobility.cli download
uv run python -m mobility.cli validate
uv run python -m mobility.cli join
uv run python -m mobility.cli features
uv run python -m mobility.cli tune
uv run python -m mobility.cli train-baselines
uv run python -m mobility.cli train-arms
uv run python -m mobility.cli train-nn
uv run python -m mobility.cli transfer
uv run python -m mobility.cli build-serving-artifact
uv run python -m mobility.cli evaluate
uv run python -m mobility.cli dq-report

# DVC equivalent and offline tests
uv run dvc repro
uv run dvc metrics show
uv run pytest . -q
```

The first run downloads about 1.5 GB: 12 monthly Parquet files, the zone lookup,
and NOAA weather. `data/raw/checksums.json` pins the inputs and every run
verifies them.

## Design

The pipeline validates each monthly extract, aggregates trips to the complete
zone-hour grid, joins weather, and builds lag and calendar features. Temporal
validation uses an embargoed train-side window; the Q4 test window remains
outside model and serving selection.

The serving command writes the tuned yellow GBM and p90 model, a green-taxi
bundle trained on green's own history, zone reference data, and a typed
`services.json` registry. The API accepts `service=yellow|green`, defaulting to
yellow and rejecting unknown services with 422. See [DESIGN.md](DESIGN.md) for
scale decisions, alternatives, SLOs, and history.

## Results

The holdout contains **584,855 zone-hours**. MAE and RMSE use pickups/hour;
lower is better. The baseline is same-hour-yesterday persistence (`naive_lag24`).

| run | MAE | RMSE | MAPE | MASE | ΔMAE vs naive |
|---|---:|---:|---:|---:|---:|
| naive_lag24 | 6.517 | 23.367 | 89.4% | 1.063 | — |
| gbm_mean | 4.667 | **15.096** | 62.0% | 0.761 | −28.4% |
| **gbm_tuned (served)** | 4.676 | 15.189 | 61.6% | 0.763 | **−28.3%** |
| gbm_xgb_tuned | 4.487 | 14.785 | 58.2% | 0.732 | −31.2% |
| gbm_lgbm_tuned | 4.582 | 14.794 | 59.9% | 0.747 | −29.7% |
| temporal_net | 5.510 | 19.686 | **54.5%** | 0.899 | −15.5% |
| temporal_net_tuned | **5.178** | 21.580 | 57.5% | 0.845 | −20.5% |

The served model removes **28.3% of MAE** versus persistence. Its 90% upper
band covers **90.8%** of holdout zone-hours. Coverage is 91.4% in Manhattan,
89.6% in Queens, 88.6% in Brooklyn, and 91.4% in the Bronx. The N/A (no-borough)
bucket under-covers at 84.7%; Staten Island over-covers at 98.5%. The no-borough
bucket is distinct from the demand-sparse conformal tercile.

The XGBoost and LightGBM challengers lose to the incumbent on validation MAE
(3.182 and 3.173 versus 3.165), so serving stays with `gbm_tuned` even though
they score lower on the Q4 test window. Selecting on that test result would be
test-set selection. The challengers run in a torch-free subprocess because
their OpenMP runtime conflicts with torch on macOS. MAPE is secondary because
zero and low-demand zone-hours make percentage errors unstable.

Predeclared post-freeze intervals use 2,000 paired resamples, seed 42, circular
seven-day blocks, and whole-zone clusters. Deltas are challenger minus baseline
MAE in pickups/hour; negative values favor the challenger and do not affect
serving.

| comparison | point ΔMAE | seven-day block 95% CI | zone-cluster 95% CI |
|---|---:|---:|---:|
| served gbm_tuned versus naive | −1.841 | [−2.338, −1.258] | [−2.464, −1.266] |
| XGBoost versus naive | −2.031 | [−2.503, −1.495] | [−2.691, −1.421] |
| LightGBM versus naive | −1.935 | [−2.433, −1.350] | [−2.606, −1.340] |
| XGBoost versus served gbm_tuned | −0.190 | [−0.265, −0.115] | [−0.240, −0.143] |

Split conformal raises second-half coverage from 90.7% to 91.5%; mean band
height above the point forecast rises from 7.032 to 7.124 pickups, a +0.091
width cost. Offsets and both coverage/width measurements remain in
`reports/metrics.json`.

Permutation importance (committed figure `reports/figures/gbm_feature_importance.json`)
ranks `lag_1` (3.31 mean MAE increase), `lag_168` (2.58), and `lag_24` (2.48)
first, with `hour` at 1.12. Weather contributes approximately zero to point MAE;
its useful evidence is the descriptive rain/dry association below.

### Green-taxi transfer and serving

The transfer study scores March 2024 on 197,160 green-taxi zone-hours. The
control model trains on green's own January–February history.

| run | MAE | RMSE | MAPE |
|---|---:|---:|---:|
| green naive lag-24 | 0.212 | 1.100 | 81.8% |
| yellow-trained gbm_mean | 0.294 | 0.911 | **66.6%** |
| yellow-trained gbm_tuned | 0.296 | 0.908 | 66.7% |
| **green-retrained gbm_green_retrained** | **0.180** | **0.688** | **66.4%** |

Yellow-trained models lose MAE to green persistence but improve RMSE and MAPE.
Retraining on green history improves all three metrics: MAE −15%, RMSE −37%,
and MAPE −19% versus green persistence. The served green bundle applies this
per-service recipe to all 534,240 curated green zone-hours.

Example API contract:

```text
POST /projects/07-open-data-mobility/forecast {"zone_id": 132, "features": {...}}
→ {"zone_id":132,"borough":"Queens","zone":"JFK Airport","prediction":223.827,"p90":251.811,"service":"yellow"}
```

Per-borough test MAE for `gbm_mean`, in pickups/hour: Manhattan 14.2, Unknown
4.5, Queens 2.2, Brooklyn 1.2, N/A 0.9, Bronx 0.5, EWR 0.3, and Staten Island
0.2. Manhattan dominates absolute error because it dominates trip volume.

## Drift observatory

The pinned serving model scores newly published TLC months without retraining:

```bash
uv run python -m mobility.cli drift-check --month 2025-03 [--fail-on-regression] [--tolerance 0.15]
```

Regression is `(month MAE − pinned MAE) / pinned MAE > drift.tolerance`.
Reports land in `reports/drift/`, with a machine-readable JSON file, DQ detail,
figures, and a running digest. Exit code 0 means within tolerance; code 1 means
a regression when `--fail-on-regression` is set; code 2 means an unpublished or
invalid month. Without the flag, a regression still writes evidence and exits 0.

| month | MAE | versus pinned 4.676 | p90 coverage |
|---|---:|---:|---:|
| 2024-11 | 5.059 | +8.2%, within tolerance | — |
| 2024-12 | 5.046 | +7.9%, within tolerance | — |
| 2025-01 | **4.442** | **−5.0%, within tolerance** | 87.4% |

The 2025-01 run also reports 59.6% MAPE and a 34.6% MAE improvement over
same-month naive persistence. Three scored months remain within tolerance.

## Weather and artifacts

For rainy hours (at least 1 mm), raw mean-pickup ratios versus dry hours are
about 0.90× for Unknown/N/A, 0.92× for Queens, and 0.93× for Staten Island.
Manhattan is 0.97×, Bronx 1.03×, and EWR 1.08×. These raw group ratios do not
normalize hour-of-week mix and are descriptive associations, not causal effects.

The report and metrics are [`reports/report.html`](reports/report.html) and
[`reports/metrics.json`](reports/metrics.json). `reports/figures/` contains the
zone-demand and per-zone MAE maps, hour-borough profiles, forecast fans, p90
calibration, feature importance, transfer, and model-comparison figures. The
served model contract is in [MODEL_CARD.md](MODEL_CARD.md) and SERVING.md.

## Limits

The N/A (no-borough) bucket under-covers at 84.7% against the 90% target, which
is separate from demand-sparse conformal strata. Weather contributes
approximately zero to point MAE, and the rain/dry ratios do not support causal
claims. Longer-horizon forecasts and causal weather estimates require different
study contracts.

## Common errors

| symptom | cause | fix |
|---|---|---|
| a stage above `download` fails on a missing raw parquet | stages do not fetch; `data/raw/` must be materialized first | run `uv run python -m mobility.cli download` or `uv run python -m mobility.cli all`; on a tight-RAM machine close memory hogs, since the bounded 12-month yellow slice is the supported configuration |

## Figures

| figure | file |
|---|---|
| actual vs pred top5 | [reports/figures/actual_vs_pred_top5.html](reports/figures/actual_vs_pred_top5.html) |
| borough mae | [reports/figures/borough_mae.html](reports/figures/borough_mae.html) |
| conformal coverage | [reports/figures/conformal_coverage.html](reports/figures/conformal_coverage.html) |
| eda trips profile | [reports/figures/eda_trips_profile.html](reports/figures/eda_trips_profile.html) |
| gbm feature importance | [reports/figures/gbm_feature_importance.html](reports/figures/gbm_feature_importance.html) |
| gbm vs nn | [reports/figures/gbm_vs_nn.html](reports/figures/gbm_vs_nn.html) |
| green transfer | [reports/figures/green_transfer.html](reports/figures/green_transfer.html) |
| hour borough heatmap | [reports/figures/hour_borough_heatmap.html](reports/figures/hour_borough_heatmap.html) |
| p90 band | [reports/figures/p90_band.html](reports/figures/p90_band.html) |
| p90 calibration | [reports/figures/p90_calibration.html](reports/figures/p90_calibration.html) |
| weather elasticity | [reports/figures/weather_elasticity.html](reports/figures/weather_elasticity.html) |
| zone demand map | [reports/figures/zone_demand_map.html](reports/figures/zone_demand_map.html) |
| zone fan | [reports/figures/zone_fan.html](reports/figures/zone_fan.html) |
| zone hour heatmap | [reports/figures/zone_hour_heatmap.html](reports/figures/zone_hour_heatmap.html) |
| zone residual map | [reports/figures/zone_residual_map.html](reports/figures/zone_residual_map.html) |

