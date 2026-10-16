# Urban Mobility Demand Intelligence

**Flagship — complete.** End-to-end demand nowcasting on real, messy,
GB-scale public data: 41.2M NYC yellow-taxi trips (2024) joined with NOAA
GHCN-Daily weather, engineered with lazy/streaming Polars under a 2 GB RAM
peak, gated by per-month DQ contracts, and validated with leakage-proof
temporal splits.

## Key results (temporal holdout Oct–Dec 2024, 584,855 zone-hours)

| run | MAE | RMSE | MAPE | ΔMAE vs naive |
|---|---|---|---|---|
| naive lag-24 | 6.52 | 23.37 | 89.4% | — |
| GBM mean | **4.67** | **15.10** | 62.0% | −28.4% |
| GBM tuned (30-trial Optuna, median pruning) | 4.68 | 15.19 | 61.6% | −28.3% |
| TemporalNet (torch, log1p target) | 5.51 | 19.69 | **54.5%** | −15.5% |
| TemporalNet tuned (10-trial Optuna) | **5.18** | 21.58 | 57.5% | −20.5% |

HPO ran against an embargoed train-side validation window only. GBM tuning
matched the defaults within noise (honest flat result); NN tuning bought
−6% MAE. p90 band calibration **90.8%** overall (target 90%; sparse N/A
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
