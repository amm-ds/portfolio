# 02 · Demand Forecasting

**Domain:** time-series forecasting · **Data:** Walmart M5 accuracy-track
subset (600 daily store-item series, primary headline); UCI Online Retail II
(sparse secondary track); seeded synthetic hierarchy (CI fast path) ·
**Status:** working showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

> The headline experiment now runs on the committed Walmart M5 subset — the
> dense-demand regime where ML demonstrably wins. Under protocol
> `m5_direct_v1` (10 weekly rolling origins, the last 2 scored once on a
> 28-day horizon), the selection-fitted convex ensemble beats the
> seasonal-naive floor by **−0.112 WAPE** (0.491 vs 0.603; 95% paired
> cluster bootstrap CI **[−0.122, −0.102]**) and −0.165 WRMSSE (0.597 vs
> 0.762) on 600 series (463 dense + 137 intermittent), winning in **both**
> volume classes — the mirror image of the UCI sparse track kept below as
> the secondary study, where the zero forecast stays the ceiling.

[Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting)

## What it shows

Leakage-safe, production-depth forecasting across both demand regimes. The
M5 headline track (`m5_track.py`): per-series statistical candidates
(statsforecast), per-series AutoETS/AutoCES, a global LightGBM over lags /
rolling means / calendar / price-SNAP-event exog (no series-identity
feature), and a convex ensemble fitted on the selection origins only — all
through 10 weekly rolling origins with a frozen, scored-once test pair, ADI/CV²
volume classes, WRMSSE with a documented denominator, paired-bootstrap CIs
and split-conformal 80% bands. The UCI/synthetic tracks below carry the same
discipline into the sparse regime and the CI fast path.

## Key results — M5 headline (protocol `m5_direct_v1`, committed `reports_m5/`)

Walmart M5 accuracy-track subset: top-3 stores (CA_3, CA_1, TX_2) × top-200
items by volume → 600 daily series, 2011-01-29..2016-06-19, 1,105,594 rows,
16% zero-day share; sha256-pinned subset built offline from the Nixtla
`datasetsforecast` mirror (`data_m5/`, PROVENANCE.md). Protocol: 10 weekly
rolling origins 7 days apart (8 SELECTION + the last 2 scored once as TEST —
2016-05-10 and 2016-05-17), each training on ≥ 1,096 days and scoring the
next 28 days; volume classes per series via Syntetos-Boylan ADI/CV² on the
real history up to the last selection origin. The full machine-readable
protocol is `reports_m5/evaluation_metadata.json`.

Pooled over the 2 scored-once test origins (WAPE = Σ|err| / Σ actual;
WRMSSE with the documented seasonal-naive-28 denominator — a deliberate,
stated deviation from the official M5 lag-1 scale):

| candidate | test WAPE | test WRMSSE | win rate vs naive |
|---|---|---|---|
| seasonal_naive (floor) | 0.603 | 0.762 | — |
| window_avg_28 | 0.515 | 0.619 | 82.8% |
| adida | 0.512 | 0.623 | 86.5% |
| tsb | 0.510 | 0.616 | 85.8% |
| auto_ets | 0.503 | 0.611 | 88.2% |
| auto_ces | 0.515 | 0.612 | 83.0% |
| lgbm | 0.495 | 0.599 | 88.8% |
| **convex_ensemble (champion)** | **0.491** | **0.597** | **90.2%** |

- **The gap vs the floor is significant** — 95% paired cluster bootstrap
  over series (2,000 reps): ensemble **−0.112 WAPE** (CI **[−0.122,
  −0.102]**) / **−0.165 WRMSSE** (CI **[−0.176, −0.155]**); lgbm −0.108 WAPE
  (CI [−0.120, −0.0965] — a 17.9% relative cut) / −0.163 WRMSSE (CI
  [−0.174, −0.152]). Both CIs exclude zero.
- **The champion is a selection-fitted convex ensemble** — best three of
  {lgbm, auto_ets, auto_ces} by SELECTION WAPE, weights grid-fit on a 0.05
  simplex over the selection origins: lgbm × 0.45 + auto_ets × 0.45 + auto_ces
  × 0.10 — the wave-25 feature pass + seeded Optuna tuning (`cli tune-m5`,
  selection origins only) put the global booster at the top of the pool
  (selection WAPE 0.469 vs auto_ets 0.473), and the blend adds pooling
  stability on top.
- **Win rates** — the ensemble clears the seasonal-naive floor on **90.2%**
  of series (dense 90.1%, intermittent 90.5%); every serious candidate lands
  in the 82.8–90.2% band, so on dense weekly-seasonal demand the pooled
  margin, not per-series coverage, separates the candidates.
- **Bands** — per-series scaled split-conformal 80% band (per-horizon-day
  width = 0.8-quantile of |lgbm residual| / series scale over the 8 selection
  origins, scaled back by each series' in-sample naive-28 RMSE, zero-clipped):
  lgbm covers **77.9%** of test actuals at mean width 13.53 units; the
  ensemble 77.9% at 13.41 — balanced across volume classes (lgbm dense 77.2%,
  intermittent 80.4%), slightly under the 80% target, stated as measured.
- **Both volume classes** — test WAPE dense 0.568 → 0.464, intermittent
  0.749 → 0.604: the models win in both classes here, the honest contrast to
  the sparse panel below.
- **Related work** — Makridakis et al., M5 competition companion (IJF 2022);
  the nixtla stack (statsforecast / mlforecast / datasetsforecast) powering
  every candidate; a Kaggle-competitions analysis of the M5 accuracy round
  ([arXiv:2009.07701](https://arxiv.org/abs/2009.07701)) for external
  context — global gradient-boosted models over per-series statistical fits,
  the same ordering this subset measures from the inside.

## Key results — UCI sparse track (SECONDARY; frozen holdout: test window scored once)

Real-data track — UCI Online Retail II (top 8 countries × top 200 products,
374 days, 405,416 panel rows, 89% zero share; MAE/MASE lead, MAPE reported but
not decision-grade at this zero share). The table is scored on the final
rolling-origin window (2010-10-01..2010-12-09, the holiday quarter); the
champion was selected on origins 1..3 only and every run is scored exactly
once on the test window. *How to read: lower is better everywhere; MASE
divides by the seasonal-naive's in-sample error (fit on a quieter period —
the naive itself scores 1.310 on this window, so 1.0 is not parity here);
read Δ MASE vs sn for parity with "same day last week"; bold = selected
champion.*

| run | MAE | RMSE | MAPE | MASE | Δ MAE vs sn | Δ MASE vs sn |
|---|---|---|---|---|---|---|
| naive_mean (floor) | 12.475 | 74.699 | 90.3% | 1.382 | +1.152 | +0.072 |
| naive_last (persistence) | 11.505 | 99.548 | 327.6% | 1.331 | +0.182 | +0.021 |
| seasonal_naive (lag-7) | 11.323 | 114.921 | 305.4% | 1.310 | 0.000 | 0.000 |
| ETS (Holt-Winters, damped+weekly) | 11.471 | 80.827 | 302.7% | 1.338 | +0.148 | +0.028 |
| ridge | 12.384 | 72.680 | 221.7% | 1.395 | +1.061 | +0.085 |
| hgb (default sklearn) | 9.565 | 71.700 | 260.3% | 1.085 | −1.758 | −0.225 |
| **hgb_tuned (Optuna, 56 trials) ← best** | **9.545** | **71.847** | **230.0%** | **1.078** | **−1.778** | **−0.232** |
| xgb_tuned (Optuna, 25 trials) | 9.804 | 73.287 | 277.2% | 1.118 | −1.519 | −0.192 |
| lgbm_tuned (Optuna, 25 trials) | 9.409 | 71.360 | 272.3% | 1.076 | −1.914 | −0.234 |
| temporal_net (PyTorch emb+MLP) | 11.770 | 71.849 | 183.6% | 1.305 | +0.447 | −0.005 |

*Δ vs seasonal_naive (sn) per row — negative means the run beats "same day
last week" on that metric; the best row is marked ← best.*

![The tuned HGB run tracks two representative UCI series day by day and clears the seasonal-naive floor on the test window](../assets/projects/02-demand-forecasting/forecast_vs_actual.png){ width="100%" }

Synthetic track — seeded CI fast path (24 series × 4 origins, seed 42; note
what clean data does to the statistical baselines). Same frozen protocol: bars
are test-window numbers, champion selected on origins 1..3. *How to read: same
metrics on clean seeded data; bold = track champion (ETS overall; temporal_net
edges the ML pack on this window by 0.1 units — fold-noise level).*

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_mean (floor) | 35.946 | 48.639 | 48.26% | 3.755 |
| naive_last (persistence) | 16.223 | 22.238 | 19.47% | 1.695 |
| seasonal_naive (lag-7) | 11.780 | 16.689 | 13.98% | 1.231 |
| **ETS (Holt-Winters, damped+weekly)** | **8.924** | **12.691** | 10.37% | **0.932** |
| ridge | 9.705 | 13.706 | 11.92% | 1.014 |
| hgb | 9.549 | 13.380 | 11.58% | 0.998 |
| hgb_tuned (Optuna, 56 trials) | 9.472 | 13.269 | 11.51% | 0.990 |
| xgb_tuned (Optuna, 25 trials) | 9.525 | 13.372 | 11.59% | 0.995 |
| lgbm_tuned (Optuna, 25 trials) | 9.341 | 13.101 | 11.31% | 0.976 |
| temporal_net (PyTorch emb+MLP) | 9.244 | 12.908 | 11.38% | 0.966 |

- **Cross-track rankings reversed under the frozen protocol — in both
  directions**: the old pooled ladder claimed the best synthetic ML run
  ranked fourth on real data; on the one-shot test window
  `lgbm_tuned` posts the best MAE of all runs (9.409, ahead of the selection
  champion 9.545 — a 1.4% gap inside fold noise), while the synthetic overall
  champion `ets` ranks 6th on UCI (11.471). Configs tuned on clean synthetic
  demand behave differently on intermittent real demand; neither pooled nor
  single-window rankings should be read as more than what they are.
- ETS wins the synthetic test window outright (MASE 0.932) and loses to its
  own seasonal naive on UCI (11.471 vs 11.323, MASE 1.338) — 89% zeros break
  the smooth-seasonality assumption. Both verdicts reported.
- HPO improved on hgb in **every** fold on synthetic (8.619 → 8.529, −1.0%
  pooled legacy); on the synthetic test window the NN edges every ML run
  (9.244) without threatening ETS — reported, not hidden.
- Probabilistic 80% band, coverage AND width on the test window: quantile
  band 0.727 synthetic / 0.919 UCI (pooled); zero-aware split-conformal
  horizon set **0.741 synthetic (avg width 26.5 units, under-covers) / 0.861
  UCI (avg width 0.00 — degenerate)** against the 0.80 target. On UCI the
  champion's median forecast is 0 on ~100% of rows, so the band collapses to
  the point forecast — the honest limit, stated on the figure, whose buttons
  drop the band interactively.
- **Multi-step headline (wave 19 rebuild + wave 20 peak candidates + wave 21
  LightGBM arms/ensemble/win rates + wave 22 baselines/metrics, UCI
  secondary — `direct_multihorizon_v1`)**: direct per-horizon models on the
  full h ∈ {1..14} lattice (one real direct-h fit per window day) on 20 weekly
  rolling origins (16 selection + 4 scored once, no embargo gap; features
  aged ≥ h days at target−h — calendar + a peak block (7/14/28d rolling
  mean/max, days-since-last-nonzero, 28d non-zero count, 28d peak ratio) +
  wave-21 price/trading-cycle features + a wave-22 rolling block (rmean7/14/28,
  rstd14/28) + aged lags, taint-tested). ADI/CV² routing: 1,069 of 1,084
  series are lumpy and choose among the statistical methods (zero,
  seasonal_naive, Croston, SBA, TSB, ma_28, adida_sba, adida_tsb) plus six
  peak-capable ML candidates — `hgb_tweedie`, `hurdle_hgb`, `lgbm_tweedie`,
  `hurdle_lgbm`, `peak_weighted_hgb` and the honestly-losing `lgbm_poisson`
  (exp-link overflow, finite-prediction guard; 107.17 pooled MAE) — while
  the 15 erratic series choose among the direct HGB and the same ML pool
  (all 15 route to ML: 10 hurdle, 3 peak-weighted, 2 tweedie). Lumpy
  champion vs floor: **6.09 vs 11.07 MAE at h=7** (95% paired-bootstrap CI
  [−7.74, −2.88]), 5.80 vs 10.64 at h=14; routing beats the unrouted all-HGB
  ladder by 3.98 MAE (CI [3.34, 4.76]) with zero the most-picked method (945
  of 1,069 lumpy series). The wave-22 baselines lose honestly: pooled MAE
  ma_28 9.94, adida_tsb 9.98, adida_sba 10.73, routed_reconciled 9.97 — all
  behind zero (9.28), consistent with the independent
  [collapseindex/online-retail-forecast](https://github.com/collapseindex/online-retail-forecast)
  benchmark where seasonal-naive wins on the same dataset. On erratic the
  peak-capable models cut peak-day MAE to 278.7–295.1 vs zero 367.3 (routed
  285.6); on lumpy tweedie cuts peak-day MAE to 28.1 (vs zero 33.7) while
  trading top-5 day-ranking recall (0.44 vs 0.88) — the peak_capture block
  carries every delta with a paired bootstrap CI. Error grows with the true
  horizon (pooled 0.08 → 6.40, h=1 → h=14). Per-horizon bands report
  coverage AND width per h (pooled 0.918, conservative — sparse
  P(sale)+ladder bands never collapse; the ML candidates carry their own
  conformal bands, pooled 0.909). The wave-22 metric layer adds rmae
  (champion 0.649 vs the floor's 1.000), per-candidate M5-convention rmsse
  (routed 0.520 pooled) and a newsvendor order-quantile cost simulation
  (holding 1.0 / stockout 3.0 per unit-day, documented assumption): at
  q=0.90 erratic 1.820 vs 1.727 cost/unit against, lumpy 2.370 vs 2.243
  against; at q=0.95 erratic flips in routing's favour (−0.137, CI excludes
  zero) — MAE-optimal routing over-orders at high service levels on
  spike-driven demand; simulation, no savings claims. The earlier
  order-up-to layer (τ=0.90, holding 0.25 / stockout 4.0) tells the same
  story: erratic 1.422 vs 1.510 for the champion, lumpy 2.874 vs 2.777
  against. The nowcast ladder above stays committed as
  the labelled one-day-ahead track.
- UCI reconciliation: w=0.75 this run, incoherence 536.7 → 134.2 (coherence
  property exact); store MAE 749.1 → 719.8. Synthetic: w=0.00 this run (store
  MAE 24.133 → 24.133, incoherence 26.688 → 26.688), accuracy effect null and
  reported as such.
- 6/6 DQ gates on both tracks; synthetic evaluate ≈ 2 min, UCI ≈ 30 min
  (multi-step the bulk of it — 14 model fits × 14 horizons × 20 origins,
  joblib-parallel); M5 ≈ 22 min; 165 offline tests.

![Bars are final-holdout-window numbers — left: MAE and RMSE per run in units; right: MASE per run against the 1.0 in-sample-scale reference line (the MASE scale is the naive's in-sample error from a quieter period, NOT the naive's own holdout error — the seasonal-naive itself lands at 1.310 on this window). MAPE is omitted as unit-incompatible and zero-inflated (it stays in the table above)](../assets/projects/02-demand-forecasting/metrics_bars.png){ width="100%" }

## Artifacts

- Figures: interactive versions live in the [showcase app case study](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting);
  static artifacts (`.html` + `.json`, per track) in `reports_m5/figures/`,
  `reports/figures/` and `reports_uci/figures/`
- Metrics: `reports_m5/metrics.json` (+ `probabilistic.json`, `evaluation_metadata.json`) ·
  UCI/synthetic: `reports/metrics.json` (+ `_uci`, with `_meta` protocol block and
  `legacy_pooled_*`) · Protocol: `evaluation_metadata.json` · Report:
  `report.html` (M5: `reports_m5/report.html`) · Reconciliation: `reconciliation.json` · Probabilistic:
  `probabilistic.json` (per-horizon coverage/width + verdict) ·
  Data-generating process: `dataset_metadata.json` (UCI) · Demo payload:
  `reports_m5/demo_payload.json` (schema v4, forecast-workbench)
- Dataset cards: `data/dataset.json`, `data_uci/dataset.json` · HPO:
  `data/hpo_best.json` (+ `hpo_study.db`) · Story: `story.yaml`

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/README.md) — problem,
  design summary, real numbers, reproduce commands, client takeaways, roadmap
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/DESIGN.md) — requirements,
  options considered (global vs per-series, validation protocol, HPO, NN,
  reconciliation), the M5 protocol decisions (§N), pipeline diagram, changelog
- Dataset card: [UCI Online Retail II](../data-registry/uci-online-retail-ii.md)
- Drift response runbook: [drift-response.md](../runbooks/drift-response.md)
- Source: `projects/02-demand-forecasting/src/demand_forecasting/`
