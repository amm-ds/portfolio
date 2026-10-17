# 07 · Urban Mobility Demand Intelligence

**Domain:** data engineering + ML · **Data:** NYC TLC yellow-taxi 2024 (41.2M
trips) + NOAA GHCN-Daily weather · **Status:** flagship — complete

> **TL;DR:** NYC taxi fleet planners staging vehicles and driver shifts one hour
> ahead across 265 zones — demand must be forecast before it arrives.
> The GBM removes **28.4% of forecast error** vs "same hour last week" on a
> strict future holdout, with a 90.8%-calibrated p90 staffing band.
>
> [Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/07-open-data-mobility)

**Flagship — complete.** End-to-end demand nowcasting on real, messy,
GB-scale public data: 41.2M NYC yellow-taxi trips (2024) joined with NOAA
GHCN-Daily weather, engineered with lazy/streaming Polars under a 2 GB RAM
peak, gated by per-month DQ contracts, and validated with leakage-proof
temporal splits.

## Key results (temporal holdout Oct–Dec 2024, 584,855 zone-hours)

The GBM removes **28.4% of forecast error** vs the "same hour last week"
baseline on a strict future holdout — and the features, not the tuner, carry
the signal: 30 trials of HPO moved MAE by 0.1%. Tuned challengers (xgb/lgbm)
won on the Q4 test window but lost on the embargoed validation window, so the
serving rule kept the incumbent — switching on test results would be test-set
selection. Read the table: MASE normalises by last-week persistence error
(1.0 = no better than "same hour last week"); lower is better; the bolded row
is the served model.

| run | MAE | RMSE | MAPE | MASE | ΔMAE vs naive |
|---|---|---|---|---|---|
| naive lag-24 (persistence) | 6.52 | 23.37 | 89.4% | 1.063 | — |
| GBM mean | 4.667 | **15.096** | 62.0% | 0.761 | −28.4% |
| GBM tuned (30 Optuna trials) | 4.676 | 15.189 | 61.6% | 0.763 | −28.3% |
| GBM xgb tuned (15 trials) | **4.487** | 14.785 | 58.2% | 0.732 | **−31.2%** |
| GBM lgbm tuned (15 trials) | 4.582 | 14.794 | 59.9% | 0.747 | −29.7% |
| TemporalNet (torch, log1p target) | 5.510 | 19.686 | **54.5%** | 0.899 | −15.5% |
| TemporalNet tuned (10 trials) | 5.178 | 21.580 | 57.5% | **0.845** | −20.5% |

p90 band calibration **90.8%** overall (target 90%; sparse N/A
zones under-cover at 84.7%, flagged). Per-borough GBM MAE peaks in Manhattan
(14.2 pickups/h) where volume peaks. Permutation importance: weekly/daily lag
features dominate, weather ≈ 0 for point MAE. Weather elasticity:
outer-borough curb demand drops 7–10% in rain (Queens 0.92×, Staten Island
0.93×) while Manhattan holds (0.97×) and EWR rises (1.08×) — directional,
with documented non-causal caveats.

## Drift observatory

Monitoring is running software, not just a runbook. The scheduled Thursday
`.github/workflows/drift-observatory.yml` workflow scores each newly
published TLC month against the persisted serving model
(`mobility.cli drift-check --month YYYY-MM`, no retraining): regression
beyond the ±15% tolerance exits 1 and opens an issue per
`docs/runbooks/drift-response.md`; months not yet published exit 2.
First scored month (2024-11): +8.2% vs pinned, within tolerance — a wiring
check, since real value starts with the first unseen month. Reports
accumulate in `reports/drift/`.

## Serving

The tuned GBM pair is persisted per `SERVING.md`; the showcase API forecast
endpoint is verified live (JFK zone 132 → 223.827 point / 251.811 p90).

## Where things live

- Code + design: [projects/07-open-data-mobility](https://github.com/amm-ds/portfolio/tree/main/projects/07-open-data-mobility) — pipeline `mobility download|validate|join|features|tune|train-baselines|train-nn|evaluate|dashboard|dq-report|all`, DVC stages in `dvc.yaml`
- Dataset cards: [NYC TLC](../data-registry/nyc-tlc.md) · [NOAA GHCN](../data-registry/noaa-ghcn.md)

## Data attribution

- **NYC TLC Trip Records** — NYC TLC terms of use; free, anonymous download.
  Monthly yellow-taxi Parquet, snapshot 2026-10-12, checksum-pinned.
- **NOAA GHCN-Daily** (station USW00094728, Central Park) — public domain
  (US Government work).

Both are downloaded by the pipeline itself; nothing raw is committed to git
(DVC tracks the derived data products).
