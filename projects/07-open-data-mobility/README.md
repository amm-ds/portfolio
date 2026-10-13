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

| run | MAE | RMSE | MAPE | ΔMAE vs naive |
|---|---|---|---|---|
| naive_lag24 (persistence) | 6.517 | 23.367 | 89.4% | — |
| gbm_mean (defaults) | 4.667 | **15.096** | 62.0% | −28.4% |
| gbm_tuned (30 Optuna trials) | 4.676 | 15.189 | 61.6% | −28.3% |
| temporal_net (64-32 MLP) | 5.510 | 19.686 | **54.5%** | −15.5% |
| temporal_net_tuned (10 trials) | **5.178** | 21.580 | 57.5% | −20.5% |

- **So what (technical):** GBM HPO was honest but flat — the tuned GBM matches
  the hand-picked defaults within noise (−0.2% MAE, +0.6% MAPE), i.e. the
  validation window (Apr–May 2024) did not transfer extra signal to Q4; the
  default config was already near the achievable frontier. NN tuning bought a
  real −6.0% MAE (smaller 32-16 net, higher LR) at a −5.6% MAPE cost — the
  tuned NN is the reported NN on MAE, the untuned one remains best on MAPE.
- **So what (client):** against "same hour last week", the production GBM
  removes ~28% of forecast error city-wide; per-borough buffers can be sized
  from the calibrated p90 band.
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
197,160 zone-hours — features from green's own Jan–Feb history):

| run | MAE | RMSE | MAPE |
|---|---|---|---|
| naive lag-24 (green persistence) | **0.212** | 1.100 | 81.8% |
| gbm_mean (yellow-trained) | 0.294 | 0.911 | **66.6%** |
| gbm_tuned (yellow-trained) | 0.296 | **0.908** | 66.7% |

- **Honest finding: transfer is mixed.** Yellow-trained GBMs *lose* MAE to
  green persistence (green demand is an order of magnitude sparser and
  burst-light, so yellow's burst-tuned patterns add noise) but *win* RMSE
  (−17%) and MAPE (−19%) — they trim the big errors. Per-service retraining
  on green history is advised before production use. Figure:
  `reports/figures/green_transfer`.

Serving (showcase API): `uv run python -m mobility.cli build-serving-artifact`
persists the tuned GBM pair + zone reference to `reports/models/serving/`
(contract: SERVING.md). Live endpoint verified:

```
POST /projects/07-open-data-mobility/forecast {"zone_id": 132, "features": {...}}
→ {"zone_id":132,"borough":"Queens","zone":"JFK Airport","prediction":223.827,"p90":251.811}
```

Per-borough test MAE (gbm_mean): Manhattan 14.2, Unknown 4.5, Queens 2.2,
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
`eda_trips_profile` (hour-of-day × borough profile), `zone_hour_heatmap`
(borough-grouped top-30 zones × hour-of-week), `actual_vs_pred_top5`,
`borough_mae`, `weather_elasticity`, `p90_band`, `p90_calibration`
(coverage vs 90% target), `gbm_feature_importance`, `gbm_vs_nn`. Full report:
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
uv run python -m mobility.cli download|validate|join|features|tune|train-baselines|train-nn|transfer|build-serving-artifact|evaluate
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
