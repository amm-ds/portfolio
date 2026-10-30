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

Run ladder on the temporal holdout (pickups/hour; lower is better), tuned
variants configured by Optuna HPO on an embargoed train-side validation
window (DESIGN.md §Hyperparameter optimisation):

| run | MAE | RMSE | MAPE | MASE | ΔMAE vs naive |
|---|---|---|---|---|---|
| naive_lag24 (same hour yesterday) | 6.517 | 23.367 | 89.4% | 1.063 | — |
| gbm_mean (defaults) | 4.667 | **15.096** | 62.0% | 0.761 | −28.4% |
| **gbm_tuned (30 Optuna trials; served)** | 4.676 | 15.189 | 61.6% | 0.763 | −28.3% |
| gbm_xgb_tuned (15 trials) | 4.487 | 14.785 | 58.2% | 0.732 | −31.2% |
| gbm_lgbm_tuned (15 trials) | 4.582 | 14.794 | 59.9% | 0.747 | −29.7% |
| temporal_net (64-32 MLP) | 5.510 | 19.686 | **54.5%** | 0.899 | −15.5% |
| temporal_net_tuned (10 trials) | **5.178** | 21.580 | 57.5% | 0.845 | −20.5% |

MAE/MAPE are scale-dependent; MASE normalises by the in-sample
seasonal-naive-24 error (≈6.13 pickups/hour), so every run is readable as a
fraction of "how wrong is same-hour-yesterday persistence" — 1.0 = no better
than persistence. Lag 24 is yesterday; lag 168 is the separate last-week feature.

- **Challenger arms (wave 11):** xgb/lgbm tuned on the identical embargoed
  validation window (Apr 22+ fold, 500k-row cap, test untouched). Both lost to
  the incumbent *on validation* (xgb 3.182 vs 3.165; lgbm 3.173 vs 3.165), so
  per the serving rule the live artifact stays `gbm_tuned` — yet on the Q4 test
  window both challengers *do* beat it (xgb −4.1% MAE). That inversion is
  exactly why the serving rule keys on validation, not test: switching on test
  results would be test-set selection. Arms run in a torch-free subprocess —
  xgboost/lightgbm's OpenMP runtime cannot coexist with torch's in one process
  on macOS (documented in DESIGN.md).

- **So what (technical):** GBM HPO was honest but flat — the tuned GBM matches
  the hand-picked defaults within noise (−0.2% MAE, +0.6% MAPE), i.e. the
  validation window (Apr–May 2024) did not transfer extra signal to Q4; the
  default config was already near the achievable frontier. NN tuning bought a
  real −6.0% MAE (smaller 32-16 net, higher LR) at a −5.6% MAPE cost — the
  tuned NN is the reported NN on MAE, the untuned one remains best on MAPE.
- **So what (client):** against "same hour yesterday", served `gbm_tuned`
  removes 28.3% of forecast error city-wide (MAE 4.676, MASE 0.763);
  per-borough buffers can be sized from the calibrated p90 band.
- **p90 uncertainty band calibration: 90.8%** overall (target 90%). By borough:
  Manhattan 91.4%, Queens 89.6%, Brooklyn 88.6%, Bronx 91.4% — tight; the
  sparse N/A zones under-cover at 84.7% (bands too tight where data is thin)
  and Staten Island over-covers at 98.5%. Flag N/A-zone bands before using
  them for staffing there.
- **Permutation importance (tuned GBM):** recent-hour momentum dominates —
  lag_168 (0.80) > lag_24 (0.64) > lag_1 (0.55) > hour (0.32); weather
  features ≈ 0 for point MAE (their value is the elasticity analysis, not
  point accuracy).

Cross-service transfer (green taxi, March 2024, yellow-trained models,
197,160 zone-hours — features from green's own Jan–Feb history; plus a
green-trained control arm fit on that same Jan–Feb history):

| run | MAE | RMSE | MAPE |
|---|---|---|---|
| naive lag-24 (green persistence) | 0.212 | 1.100 | 81.8% |
| gbm_mean (yellow-trained) | 0.294 | 0.911 | **66.6%** |
| gbm_tuned (yellow-trained) | 0.296 | 0.908 | 66.7% |
| **gbm_green_retrained (green Jan–Feb)** | **0.180** | **0.688** | **66.4%** |

- **Honest finding: yellow-to-green transfer is mixed — and the control
  settles why.** Yellow-trained GBMs *lose* MAE to green persistence (green
  demand is an order of magnitude sparser and burst-light, so yellow's
  burst-tuned patterns add noise) but *win* RMSE (−17%) and MAPE (−19%). A GBM
  fit on green's own two months of history (`gbm_green_retrained`, default GBM
  family, 337k zone-hours) beats green persistence on **all three** metrics —
  MAE 0.180 vs 0.212 (−15%), RMSE 0.688 vs 1.100 (−37%), MAPE 66.4% vs 81.8%
  — so the transfer gap is a service-distribution problem with a measured fix,
  not a law of sparse demand: retrain per service before transfer. Figure:
  `reports/figures/green_transfer`.

Serving (showcase API): `uv run python -m mobility.cli build-serving-artifact`
persists the tuned GBM pair + zone reference to `reports/models/serving/`
(contract: SERVING.md). Live endpoint verified:

```
POST /projects/07-open-data-mobility/forecast {"zone_id": 132, "features": {...}}
→ {"zone_id":132,"borough":"Queens","zone":"JFK Airport","prediction":223.827,"p90":251.811,"service":"yellow"}
```

Per-service retraining is productionized (wave 15): the same command also
fits the green bundle — the measured wave-14 control recipe (default GBM
family on the service's own history + quantile-0.9 p90 twin) over all
534,240 curated green zone-hours — and persists it under
`reports/models/serving/green/` in the identical three-file contract, plus a
typed `services.json` registry (`mobility.schemas.ServingRegistry`) indexing
`yellow` (root, dir `.`) and `green` (dir `green`). The showcase API's
loader is directory-parameterized, so the green bundle is loadable as-is;
`mobility.serving.predict_service(cfg, service, zone_id, features)` is the
typed mobility-side reference for per-service inference (unknown zone /
missing features raise `ValueError`, mirroring the API's 422s). The
showcase API endpoint routes per service now: the forecast request accepts
an optional `service=yellow|green` field (default yellow), resolved through
the `services.json` registry and echoed in the response (unknown service →
422); apps/showcase-api tests pin default-yellow parity, green routing
against the committed green bundle, and unchanged readiness.

Per-borough test MAE (gbm_mean): Manhattan 14.2, Unknown 4.5, Queens 2.2,
Brooklyn 1.2, N/A 0.9, Bronx 0.5, EWR 0.3, Staten Island 0.2 pickups/hour.
Manhattan dominates absolute error because it dominates volume (≈60 pickups/h
per zone at peak); relative error there is comparable to other boroughs.

## Drift observatory

The pinned serving model is scored against **every newly published TLC month**
— no retraining: the drift question is whether the artifact still works on
unseen data. The scheduled `.github/workflows/drift-observatory.yml` Action
runs weekly (plus manual dispatch):

```bash
uv run python -m mobility.cli drift-check --month 2025-03 [--fail-on-regression] [--tolerance 0.15]
```

The month's parquet is fetched through the checksum machinery (one file,
bounded), lightly re-validated, aggregated to the zone-hour grain, featurised
exactly like training, and scored with the persisted serving bundle; MAE/MAPE
are compared against naive lag-24 on the same rows and against the pinned
test-window metrics in `reports/metrics.json`. Regression =
(month MAE − pinned MAE)/pinned MAE > `drift.tolerance` (`params.yaml`,
`--tolerance` overrides).

Exit codes (the Action's contract): **0** within tolerance; **1** regression
beyond tolerance — only with `--fail-on-regression` (the Action then opens an
issue per `docs/runbooks/drift-response.md`); **2** month not published yet
(HTTP 404, or the CDN's 403 for a missing key — TLC files land ~2 months
late) or bad `--month` — skip-worthy, no issue. Without
`--fail-on-regression` a regression still writes its report and exits 0, for
manual runs.

Artifacts per scored month in `reports/drift/`: `<month>.json` (machine
report), `<month>_mae.html`/`.json` (themed figure vs the pinned baseline),
`<month>.dq.json` (gate detail), and a running `DRIFT.md` digest. The manual
DVC stage (`dvc repro drift_check`, month from `params.yaml` `drift.month`)
writes the same `reports/drift` out. Months scored so far: 2024-11 — MAE
5.059 vs pinned 4.676 (+8.2%, within tolerance); 2024-12 — MAE 5.046 vs
pinned 4.676 (+7.9%, within tolerance); and the first genuinely unseen month
**2025-01**, fetched live through the checksum machinery — MAE **4.442** vs
pinned 4.676 (**−5.0%**, within tolerance), MAPE 59.6%, ΔMAE vs naive +34.6%,
p90 coverage 87.4% (slight under-cover vs the 90% target). Unseen-window
behavior is now measured: three months scored, none regressed, so the alarm
path remains unwalked only because no month has exceeded tolerance.

Weather elasticity (mean hourly pickups, rain ≥1 mm vs dry, test window):

- Outer areas drop most in rain: `Unknown`/N/A zones ≈ 0.90×, Queens 0.92×,
  Staten Island 0.93×.
- Manhattan is resilient (0.97×) — dense transit/walking alternatives keep
  curb demand stable; Bronx (1.03×) and EWR (1.08×) *rise*, consistent with
  airporter substitution to taxis.
- Caveat: raw groupby ratios, hour-of-week mix not normalised — directional,
  not causal.

Figures (interactive HTML + showcase JSON) in `reports/figures/`:
`hour_borough_heatmap` (hour-of-day × borough mean-pickups heatmap, lead
results figure), `eda_trips_profile` (hour-of-day × borough profile), `zone_hour_heatmap`
(borough-grouped top-30 zones × hour-of-week), `zone_demand_map` and
`zone_residual_map` (TLC-zone choropleths of demand geography and per-zone
MAPE), `zone_fan` (mean + p90 forecast fan for the busiest zones),
`actual_vs_pred_top5`, `borough_mae`, `weather_elasticity`, `p90_band`,
`p90_calibration` (coverage vs 90% target), `gbm_feature_importance`,
`gbm_vs_nn`. Full report: `reports/report.html`; metrics:
`reports/metrics.json` (MAE/RMSE/MAPE + MASE). The served model is documented
in [MODEL_CARD.md](MODEL_CARD.md).

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
uv run python -m mobility.cli download|validate|join|features|tune|train-baselines|train-arms|train-nn|transfer|build-serving-artifact|evaluate
uv run python -m mobility.cli dq-report   # print/persist the latest DQ digest
```

DVC equivalent: `dvc repro` (stages mirror the CLI in `dvc.yaml`,
`params.yaml` mirrors `MobilityConfig`); `uv run dvc metrics show` prints the
run-ladder metrics from the committed `metrics:` declaration. Tests need no network:

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

## Roadmap

- **Delivered:** streaming 41.2M-trip pipeline with the temporal run ladder,
  p90 calibration (90.8% coverage) and the served `gbm_tuned` artifact.
- **Delivered:** green-transfer study plus the per-service retraining control
  (`gbm_green_retrained` beats green persistence on MAE/RMSE/MAPE at two
  months of green history); drift observatory scored 2024-11 (+8.2%) and
  2024-12 (+7.9%) in-window against the pinned artifact.
- **Delivered (wave 15):** the first genuinely unseen drift month —
  2025-01, fetched live through the checksum machinery — scored in-window
  (MAE 4.442 vs pinned 4.676, −5.0%; p90 coverage 87.4%); and per-service
  retraining productionized as the `gbm_green_served` serving bundle +
  typed `services.json` registry + `predict_service` reference
  implementation.
- **Delivered:** the showcase API forecast endpoint routes per service — the
  request accepts an optional `service=yellow|green` field (default yellow),
  resolved through the `services.json` registry and echoed in the response
  (unknown service → 422); apps/showcase-api tests pin default-yellow parity,
  green routing against the committed green bundle, and unchanged readiness.
- **Deferred:** causal weather claims and longer-horizon forecasts —
  different study contracts, not tuning knobs.
