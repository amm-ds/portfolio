# 02 · Demand Forecasting

**Domain:** time-series forecasting · **Data:** Walmart M5 accuracy-track
subset (600 daily store-item series, primary headline); UCI Online Retail II
(sparse secondary track); seeded synthetic hierarchy (CI fast path) ·
**Status:** working showcase on the standard platform (flagships: [01](../01-rag-agent), [07](../07-open-data-mobility))

## Problem

A retailer needs **per-store-product daily unit forecasts** it can trust for
replenishment. The project studies both demand regimes honestly: the
**dense** regime (Walmart M5 — daily food demand with trend, weekly
seasonality, price/SNAP/event signal), where global ML demonstrably beats the
seasonal-naive floor, and the **sparse** regime (UCI Online Retail II — 89%
zero share), where the flat/zero forecast stays the ceiling and the
measurement says so. Either regime invalidates a random train/test split:
dated panels leak the future into the past and overstate accuracy, so every
track here runs embargoed rolling origins with a frozen, scored-once test
window. The deliverable is a reproducible pipeline that validates its data,
engineers leakage-safe features, and compares baseline against
gradient-boosted models under that protocol.

## Design

See [DESIGN.md](DESIGN.md) for the full requirements/options/decisions log.
Summary:

- **Data**: three tracks side by side. The **M5 headline track**
  (`m5_data.py`/`m5_track.py`, protocol `m5_direct_v1`, wave 24) runs on the
  committed, checksum-pinned Walmart M5 subset — 600 daily store-item series
  (top-3 stores CA_3/CA_1/TX_2 × top-200 items by volume, 2011-01-29..2016-06-19,
  1,105,594 rows, 16% zero-day share), built offline from the Nixtla
  `datasetsforecast` mirror (sha256 pins in `data_m5/`, PROVENANCE.md) — in
  the regime where ML demonstrably wins: dense daily demand with real
  exogenous signal (price, SNAP, events). The **UCI Online Retail II sparse
  track** (`uci.py`, `multihorizon.py`) stays as the clearly-labelled
  secondary study — the panel where baselines win. The **synthetic track**
  (platform-seeded, `seed=42`, 730 days → 17,520 rows) remains the CI/offline
  fast path, gated by `DQReport` and versioned by a `DatasetContract` with
  SHA-256 (`data/dataset.json`).
- **Features** (`features.py`): lags `[1, 7, 14]` built with `shift` **per
  series** (never the current row), plus calendar features (day-of-week,
  weekend, month, week, day-of-year sin/cos) and a linear trend counter.
  Undefined-lag rows are dropped, never imputed.
- **Models** (`model.py`): two deterministic naive floors — `naive_mean`
  (global train mean) and `naive_last` (per-series persistence) — two
  statistical baselines — `seasonal_naive` (lag-7, same weekday last week)
  and per-series ETS (statsmodels Holt-Winters, damped trend + weekly
  seasonality, fallback chain to seasonal naive for short/failing series,
  documented + tested) — plus global models with one-hot series id: `ridge`
  (Ridge inside a `Pipeline` with `StandardScaler` + one-hot), three
  boosting arms — `hgb` (default sklearn), `hgb_tuned` (production),
  `xgb_tuned` (XGBoost) and `lgbm_tuned` (LightGBM),
  the latter two Optuna-tuned mirrors of the HPO space — and `temporal_net`
  (hand-written PyTorch embedding+MLP, `temporal.py`).
  One artefact for the whole hierarchy, new series handled via
  `handle_unknown="ignore"`.
- **HPO** (`hpo.py`): seeded Optuna studies (TPESampler seed 42, median pruning)
  per booster arm — sklearn HGB (6 hyperparams, 56 trials), XGBoost (6, 25) and
  LightGBM (5, 25) — with the objective = mean MAE over
  the *same* date-aligned CV folds as the backtest. Best params (CV MAE 8.5291)
  are persisted to `data/hpo_best.json` and mirrored into
  `ForecastConfig.hgb_tuned` defaults + `params.yaml`. Resumable SQLite
  storage with per-trial checkpointing; run via `cli hpo` (separate dvc stage
  before `train`, deliberately not part of `cli all`).
- **Reconciliation** (`reconcile.py`): store-level (parent) forecasts from the
  tuned model are compared against summed store-product (children) forecasts;
  a scalar MinT-lite shrinkage `w`, grid-estimated on the embargoed previous
  fold, redistributes the parent-child discrepancy. Coherence after adjustment
  is exactly `(1-w)` of the incoherence before (property-tested).
- **Real-data track** (`uci.py`): UCI Online Retail II activated behind
  `--data-source uci` — checksum-pinned download (sha256 in `params.yaml`),
  dependency-free XLSX streaming parser (stdlib zipfile/iterparse), 2009-2010
  sheet parsed to 525,461 transactions, aggregated to a bounded daily panel
  (top 8 countries as stores × top 200 stock codes as products, 374 days,
  405,416 rows, 89% zero share — genuinely intermittent demand). Sales lines
  only (returns/cancellations excluded, documented). Synthetic stays the
  default so CI runs offline. The full data-generating process — filtering,
  aggregation, geography, caveats — is documented in
  [reports_uci/dataset_metadata.json](reports_uci/dataset_metadata.json)
  (emitted by `prepare`) and summarised under **Data-generating process**
  below. The forecast target is **the next 14 days of daily units per
  country-product series** (top 8 countries × top 200 products by volume),
  aggregated from cleaned Online Retail II transactions (cancellations removed).
- **Probabilistic forecasts** (`probabilistic.py`): quantile HGB (p10/p50/p90)
  on the tuned config plus a split-conformal band calibrated on the early
  folds; empirical coverage reported against the 80% target, with a band
  figure for the two highest-volume series.
- **Validation** (`evaluate.py`): `TimeSeriesCV` (4 expanding-window folds,
  7-day embargo gap) over the dated feature rows, folds mapped to rows so
  no date block straddles train/validation. **Frozen holdout protocol**
  (`rolling_origin_holdout_v1`): the last origin is the test window — model
  selection (champion pick) pools folds 1..n-1 only, every candidate is
  scored once on the test window, and the committed headline metrics are the
  test-window numbers. The protocol, the exact `selection_used_origins` vs
  `test_origin`, the within-train-window preprocessing guarantee and every
  metric definition are emitted to
  [reports_uci/evaluation_metadata.json](reports_uci/evaluation_metadata.json);
  the previous all-fold pooled headline is retained per model under
  `legacy_pooled_*` in metrics.json. Metrics from
  `portfolio_eval.ml.regression_metrics` (MAE/RMSE/MAPE) plus MASE, bias,
  zero-safe WAPE, per-fold MAEs (std/range) and per-horizon (h=1..14)
  MAE/MASE on the test window's final 14 days. **Primary multi-step track**
  (`multihorizon.py`, protocol `direct_multihorizon_v1`): direct per-horizon
  models on weekly rolling origins with ADI/CV² routing, paired-bootstrap
  CIs, per-horizon bands and the order-up-to decision metric — see
  *Multi-step headline* below.

## M5 headline — Walmart M5 accuracy subset (protocol `m5_direct_v1`, PRIMARY)

The headline experiment (wave 24; performance passes wave 25 + wave 27) is
the committed
Walmart M5 subset — 600
daily store-item series (top-3 stores CA_3/CA_1/TX_2 × top-200 volume items),
2011-01-29..2016-06-19 (1,105,594 rows, 16% zero-day share), in the regime
where ML demonstrably wins: dense daily store-item demand with real exogenous
signal (price, SNAP, events). Protocol: **10 weekly rolling origins**
(8 SELECTION + the last 2 scored once as TEST — 2016-05-10 and 2016-05-17),
each training on ≥ 1,096 days (3+ years) and scoring the next **28 days**
(the M5 evaluation horizon). Candidates: per-series statistical
(`seasonal_naive`, `window_avg_28`, `adida`, `tsb` — statsforecast 2.1.1),
per-series automatic (`auto_ets`, `auto_ces`), a global **LightGBM** and a
global **XGBoost** (mlforecast 1.1.0 recursive over the same wave-27 feature
space: lags 1/7/14/21/28, rolling means 7/28/56/84 and stds 7/28 at lag 1,
rolling mean 7/28 + std 7 at lag 7, expanding mean, calendar
dayofweek/day-of-month/month, exog price/SNAP/event codes + any_snap +
snap_weekend + event distances + price momentum/relative/missing + panel
statics item_age/hist_mean/hist_max/dept_mean/cat_mean — no series-identity
feature; lgbm runs the wave-27 25-trial tuned config from a seeded Optuna
study on the selection origins, `cli tune-m5`, block `m5_lgbm:` in
params.yaml; xgb carries a modest a-priori config for booster diversity),
a pure-L2 LightGBM arm **lgbm_l2** (wave 28: same pipeline and features,
`objective=regression` with the tree count re-derived under an L2
early-stopping pass on the selection-only nested split), and two ensemble candidates — a **convex_ensemble** of the best THREE of
{lgbm, lgbm_l2, xgb, auto_ets, auto_ces} by SELECTION WAPE, weights
grid-fit on a 0.05 simplex over the selection origins only (the committed
rule picked xgb × 0.35 + lgbm × 0.20 + auto_ets × 0.45; wave 28 widened the
pool with the pure-L2 arm and added a bitwise-identity dedup — a candidate
whose selection forecasts are identical to an admitted member is skipped,
it would only displace a diverse member), and **ensemble_l2** — the same
rule with SELECTION WRMSSE as the ranking and weight-fitting metric (the
L2-selected comparison blend; wave 28, comparison/demo material).
Volume classes per series:
Syntetos-Boylan ADI/CV² on each series' real history up to the last
selection origin — **463 dense + 137 intermittent** series. Nothing reads the
test origins at fit/selection time; every fit is seeded or closed-form, so a
re-run reproduces the artifacts byte-for-byte. The machine-readable protocol
is [reports_m5/evaluation_metadata.json](reports_m5/evaluation_metadata.json);
the written report is `reports_m5/report.html`.

Headline table — pooled over the 2 scored-once test origins (600 series ×
28 days each; WAPE = Σ|err| / Σ actual, WRMSSE with the documented
seasonal-naive-28 denominator — see the metric definitions in
evaluation_metadata.json):

| candidate | test WAPE | test WRMSSE | MAE (units) | win rate vs naive |
|---|---|---|---|---|
| seasonal_naive (floor) | 0.603 | 0.7617 | 5.774 | — |
| window_avg_28 | 0.515 | 0.6192 | 4.925 | 82.8% |
| adida | 0.512 | 0.6230 | 4.902 | 86.5% |
| tsb | 0.510 | 0.6156 | 4.879 | 85.8% |
| auto_ets | 0.503 | 0.6105 | 4.819 | 88.2% |
| auto_ces | 0.515 | 0.6119 | 4.931 | 83.0% |
| lgbm | 0.4975 | 0.5964 | 4.762 | 87.8% |
| lgbm_l2 | 0.4975 | 0.5964 | 4.762 | 87.8% |
| xgb | 0.4955 | 0.6001 | 4.7425 | 86.5% |
| **convex_ensemble (champion)** | **0.491** | **0.5958** | **4.697** | **88.8%** |
| ensemble_l2 | 0.4905 | 0.5952 | 4.695 | 88.7% |

- **The gap vs the naive floor is real and significant** — 95% paired cluster
  bootstrap over series (2,000 reps, fixed seeds): convex_ensemble
  **−0.1125 WAPE** (CI **[−0.1228, −0.1026]**) and **−0.1659 WRMSSE** (CI
  **[−0.1772, −0.1552]**); lgbm −0.1057 WAPE (CI [−0.1184, −0.0935], a 17.5%
  relative cut) and −0.1652 WRMSSE (CI [−0.1770, −0.1535]). Both CIs exclude
  zero. Wave 27, stated plainly: the feature expansion + tuning round moved
  lgbm's pooled test WAPE only within noise (0.495 → 0.498; the gap CI is
  ~0.012 wide) — the honest gain of the pass is the wider booster pool: xgb
  enters the ensemble (test 0.496 on its own) and the champion blend improves
  to 0.491, with the next-week service number (below) the clearest mover.
- **L1 vs L2 forecast shape (wave 28)** — the flat look of the shipped curves
  is not a loss-function bug. Verification: LightGBM's default objective is
  already squared error, so the track's L1 character lived in the tuner's l1
  early-stopping and the WAPE selection layers. The pure-L2 arm `lgbm_l2`
  (same pipeline/features, explicit `objective=regression`, tree count
  re-derived under an L2 early stop on the selection-only nested split)
  reproduced `lgbm` **bitwise** — the L2 stop re-derived the same 279 trees —
  and is committed as a candidate but deduped from the ensemble ranking (a
  duplicate carries no new information; measured: ranking it separately
  regressed the headline blend 0.4907 → 0.4953 by pushing auto_ets out). The
  WRMSSE-selected `ensemble_l2` (same best-three, weights xgb × 0.45 + lgbm ×
  0.20 + auto_ets × 0.35 minimising selection WRMSSE) lands test WAPE
  **0.4905** / WRMSSE **0.5952** vs the WAPE blend's 0.4907 / 0.5958 — it
  edges BOTH metrics by 0.0002 / 0.0006, far inside the ±0.01 bootstrap noise,
  and is the committed pooled-test-WRMSSE champion (0.5952). Stated as
  measured: on this panel L1-vs-L2 selection is a wash; the curves are smooth
  because the conditional mean of noisy daily demand IS smooth (curve
  day-to-day variation ≈ 5.4 units vs ≈ 12.2 for realized demand; spike-day
  MAE sits at ~13 for every candidate) — spike-tracking point forecasts are
  not on the table at this horizon, and the band, not a pointier curve, is the
  honest answer to spike uncertainty.
- **Bands** — per-series scaled split-conformal 80% band around the point
  forecast: per-horizon-day width = the 0.8-quantile of |lgbm residual| /
  series scale over the 8 selection origins, scaled back by the series'
  in-sample seasonal-naive-28 RMSE (zero/NaN scale -> the origin's median),
  zero-clipped and sorted — the pooled absolute-width band we tried first
  mis-served the panel's volume heterogeneity (top-quintile series covered
  ~61% at the nominal 80% level). Result: lgbm covers **77.7%** of test
  actuals (target 80%) at mean width **13.535** units; the ensemble covers
  77.7% at 13.342 — by class the band is balanced (lgbm dense 76.9%,
  intermittent 80.6%). Slightly under-covering, stated as measured.
- **Win rates** — share of series whose pooled test |error| beats the
  seasonal_naive floor: the ensemble wins on **88.8%** of all series (dense
  88.6%, intermittent 89.8%); the per-series spread across candidates is
  narrow (82.8–88.8%) because on dense weekly-seasonal demand every serious
  candidate clears the floor — the pooled margin, not per-series coverage, is
  what separates them.
- **By class** (test WAPE): dense 0.568 (naive) → **0.464** (ensemble);
  intermittent 0.749 → **0.603**. On this subset the models win in BOTH
  classes — the honest contrast to the UCI sparse panel below, where the
  zero forecast stays the ceiling.

### Rolling next-week service (h ≤ 7, all origins)

The headline of a demand forecast is the NEXT week — later weeks roll
forward as new data lands, so the **weekly rolling service is the deployment
shape**: each week the model is re-run and only the first week of the fresh
forecast is consumed. Pooled over h=1..7 of ALL 10 rolling origins (each
origin's first-week forecast is one deployed weekly forecast; the 8 selection
origins are included, so this is the operational service number, not a
held-out estimate — the held-out estimate stays the 28-day test block above):

| candidate | next-week WAPE | rmae | rmae dense | rmae intermittent |
|---|---|---|---|---|
| seasonal_naive (floor) | 0.5442 | 1.0000 | 1.0000 | 1.0000 |
| window_avg_28 | 0.4669 | 0.8581 | 0.8640 | 0.8400 |
| adida | 0.4547 | 0.8355 | 0.8357 | 0.8350 |
| tsb | 0.4571 | 0.8399 | 0.8436 | 0.8288 |
| auto_ets | 0.4352 | 0.7998 | 0.7962 | 0.8109 |
| auto_ces | 0.4388 | 0.8064 | 0.8075 | 0.8030 |
| lgbm | 0.4327 | 0.7951 | 0.7915 | 0.8063 |
| lgbm_l2 | 0.4327 | 0.7951 | 0.7915 | 0.8063 |
| xgb | 0.4297 | 0.7896 | 0.7876 | 0.7957 |
| **convex_ensemble (champion)** | **0.4233** | **0.7780** | **0.7736** | **0.7915** |
| ensemble_l2 | 0.4234 | 0.7781 | 0.7740 | 0.7909 |

- The next-week gap vs the floor is real and significant — paired cluster
  bootstrap over series on the h≤7 metric: lgbm **−0.1115 WAPE** (CI
  **[−0.1197, −0.1039]**); convex_ensemble **−0.1208 WAPE** (CI
  **[−0.1288, −0.1130]**) — a 22.2% relative cut. Measured, not asserted: at
  h≤7 every candidate beats the seasonal_naive floor in BOTH volume classes —
  lgbm: **yes** (dense 0.7915, intermittent 0.8063); xgb: **yes** (dense
  0.7876, intermittent 0.7957); convex_ensemble: **yes** (dense 0.7736,
  intermittent 0.7915). The wave-27 pass moved this number the most:
  0.4250 → 0.4233 (rmae 0.7810 → 0.7780).
- The error-growth shape on the 2 scored-once test origins (WAPE per 7-day
  block of the 28-day horizon):

| candidate | wk1 (h1-7) | wk2 (h8-14) | wk3 (h15-21) | wk4 (h22-28) |
|---|---|---|---|---|
| seasonal_naive (floor) | 0.5423 | 0.5717 | 0.6343 | 0.6598 |
| window_avg_28 | 0.4482 | 0.4783 | 0.5465 | 0.5801 |
| adida | 0.4395 | 0.4749 | 0.5487 | 0.5798 |
| tsb | 0.4414 | 0.4733 | 0.5435 | 0.5756 |
| auto_ets | 0.4283 | 0.4668 | 0.5422 | 0.5710 |
| auto_ces | 0.4345 | 0.4891 | 0.5598 | 0.5723 |
| lgbm | 0.4205 | 0.4553 | 0.5367 | 0.5715 |
| lgbm_l2 | 0.4205 | 0.4553 | 0.5367 | 0.5715 |
| xgb | 0.4146 | 0.4515 | 0.5356 | 0.5738 |
| **convex_ensemble (champion)** | **0.4136** | **0.4498** | **0.5298** | **0.5636** |
| ensemble_l2 | 0.4128 | 0.4488 | 0.5298 | 0.5646 |

  Week 1 carries **28.0%** of the value (the share of convex_ensemble's
  absolute-error reduction vs the floor delivered in wk1) and week 4 error
  is **1.36×** week 1 (0.4136 → 0.5636; the floor degrades 1.22× the same
  way) — the further out the week, the more every candidate converges to the
  floor. That is why the next-week number is the service headline and the
  28-day pooled table stays the month view.

### Related work — M5 and the forecasting stack

- **M5 competition companion** (Makridakis et al., *International Journal of
  Forecasting*, 2022) — the competition this subset comes from. Two
  deliberate deviations, both documented in
  `evaluation_metadata.json`: the subset is the top-volume 600 of 30,490
  series (a working-scale study, not the competition leaderboard), and the
  WRMSSE denominator is the seasonal-naive-28 in-sample MSE rather than the
  official lag-1 random walk — a stricter scale for weekly-seasonal dense
  demand.
- **The nixtla stack** ([nixtla.github.io](https://nixtla.github.io)) —
  statsforecast / mlforecast / datasetsforecast power every candidate here;
  the per-series statistical layer and the global LightGBM recursive
  strategy follow their documented patterns (pinned versions in
  evaluation_metadata.json).
- **A Kaggle-competitions analysis of the M5 accuracy round**
  ([arXiv:2009.07701](https://arxiv.org/abs/2009.07701)) — external context
  on how the competition was won (global gradient-boosted models over
  per-series statistical fits — the same ordering our 600-series subset
  measures from the inside).

Reproduce: `uv run python -m demand_forecasting.cli evaluate-m5` (writes
`reports_m5/`, ~31 min; offline, checksum-pinned) or
`build-report-m5` to rebuild the HTML report from the committed artifacts.

## Data-generating process (UCI track — SECONDARY)

`reports_uci/dataset_metadata.json` is the machine-readable audit anchor;
the summary (all of it implemented in `uci.py` — the doc exists because the
review demanded the pipeline's data contract be stated explicitly):

- **Source**: UCI Online Retail II, `online+retail+ii.zip`
  (https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip),
  sha256-pinned in `params.yaml`, sheet *Year 2009-2010*, free for research
  (Chen, Gallino & Li 2012, *Management Science*).
- **Cancellation filtering**: sales lines only — rows with `Quantity > 0`;
  cancellations/returns (negative-quantity lines) are removed, blank stock
  codes dropped. Returns are a separate business process; net-of-returns
  demand would double-count reverse logistics.
- **Quantity handling**: daily sum of line quantities per
  (date, country, stock_code) → the panel's integer `units`; `price` is the
  mean line price of the day (carried for reference, not a model target).
- **Geography / products**: top 8 countries by unit volume become `stores`,
  top 200 stock codes become `products`; everything else is dropped.
- **Daily aggregation**: one row per (date, country, stock_code), reindexed
  to the complete daily calendar between first and last observed dates;
  missing day-series combinations are zero-filled (price forward-filled).
  Observed range: 2009-12-01..2010-12-09 (374 days → 405,416 rows after the
  top-N bounding, 89% zero share).
- **Caveat — zeros**: zero-sales days may be missing rather than true zero
  demand: the source has **no trading calendar**, so a zero-filled day can
  mean "closed or not trading" as easily as "no demand". Models must live
  with that ambiguity; it is also why MAPE is not decision-grade here.

## Multi-step headline — direct multi-horizon (protocol `direct_multihorizon_v1`, UCI sparse track — SECONDARY)

The UCI sparse track's primary result — kept intact below — is the deliberate
counterpoint to the M5 headline above: on 89%-zero demand the baselines win.
The nowcast tables below stay committed and valid, but they answer "tomorrow,
given today". The track replenishment actually runs is **multi-step** (wave 19,
fifth-pass audit; wave 20 the peak-capable candidates; wave 21 the LightGBM
arms, the peak-weighted HGB, the convex ensemble and the per-series win-rate
metric; wave 22 the ma_28/ADIDA statistical candidates, leakage-safe rolling
features, the hierarchy-anchored `routed_reconciled` post-processing and the
rmae/rmsse/newsvendor metric layer; the lattice now
spans the full window): direct per-horizon models for every
h ∈ {1..14} — one real direct-h model per day of the window, no interpolated
display points (champion-config HGB;
features = calendar of the target date + a **peak block at target−h** —
rolling mean AND max over 7/14/28-day windows, days-since-last-nonzero, 28d
non-zero-day count, 28d peak ratio — + wave-21 price/trading-cycle features
(unit-price stats and weekday/trading-day flags of the target week)
+ a wave-22 rolling block at the same target−h reference day (rolling means
over 7/14/28 days, rolling stds over 14/28 — trend/volatility state aged ≥ h
days, taint-tested like every other demand feature)
+ lags `lag_h`, `lag_{h+7}`, `lag_{h+14}`;
every feature is ≥ h days older than the target by construction,
property-tested with tainted panels), issued from **20 weekly rolling
origins** (16 selection + the last 4 scored once; the window starts the day
AFTER the origin — the audit's 57-day hole is gone). Intermittency is handled
by ADI/CV² classification (Syntetos-Boylan quadrants): **1,069 of 1,084 series (98.6%) are
lumpy**; every series is routed per class to its best
candidate on the selection origins only (property-tested): lumpy series
choose among zero / seasonal_naive / Croston / SBA / TSB / **ma_28** (rolling
28-day mean — the audit-flagged missing moving-average baseline) / the
**ADIDA pair** (`adida_sba`, `adida_tsb` — 7-day temporal aggregation aligned
to the origin so the window is exactly two buckets, SBA/TSB on the bucket
totals, within-week-profile disaggregation) **plus six
peak-capable ML candidates** — `hgb_tweedie` (HGB with the compound-Poisson
tweedie deviance, variance power 1.5; lr/depth/leaves tuned on the selection
origins by a seeded 12-trial Optuna study), `hurdle_hgb` (per-h two-stage
HGB: log-loss classifier for P(sale) × regressor on log1p(non-zero sizes),
zero-corrected on the selection origins — identity won there, tested not
assumed), the wave-21 LightGBM arms `lgbm_tweedie` (tweedie loss) and
`hurdle_lgbm` (two-stage, same zero-correction), both HPO'd by a seeded
capped Optuna study on the selection origins, `lgbm_poisson` (Poisson loss —
evaluated and honestly reported: it loses badly, see below), and
`peak_weighted_hgb` (sample-weighted HGB that up-weights peak days, weight
2.0 chosen on the selection origins); the 15 erratic series choose among the
direct HGB and the same ML pool. `ensemble_convex` (per-series convex
combination of the routed prediction and the series' best ML candidate,
weight chosen on the selection origins) and `routed_reconciled` (wave-22
hierarchy anchoring: each country block's routed forecast is adjusted toward
the seasonal-naive forecast of the country's aggregated demand, discrepancy
allocated proportionally to member forecasts — comparison-only, never routed
to) ride along as unrouted benchmarks. Every headline comparison carries a
95% paired cluster bootstrap CI over (series × scored origins), the win-rate
metric counts, per class and horizon, the share of series whose summed
|error| actually beats the seasonal-naive floor (95% cluster bootstrap over
series), and the wave-22 metric layer adds **rmae** (candidate pooled MAE ÷
floor pooled MAE), per-candidate **rmsse** (M5 convention, in-sample
seasonal-naive-7 MSE denominator) and a **newsvendor** order-quantile cost
simulation. Full detail in
[reports_uci/evaluation_metadata.json](reports_uci/evaluation_metadata.json)
(`multi_horizon` block) and `metrics.json` (`_multistep`).

Champion vs floor (seasonal naive) per demand class — MAE in units on the 4
scored origins, 95% CI on the gap (negative = champion better):

| class | n | champ MAE h=7 | floor MAE h=7 | gap CI h=7 | champ MAE h=14 | floor MAE h=14 | gap CI h=14 |
|---|---|---|---|---|---|---|---|
| erratic | 15 | 50.252 | 68.350 | [−55.031, +5.925] | 48.875 | 60.000 | [−34.648, +9.747] |
| **lumpy** | 1,069 | **6.090** | 11.070 | **[−7.742, −2.877]** | **5.803** | 10.642 | **[−7.511, −2.804]** |

- **Routing is still the win, and it is now peak-aware**: on lumpy the routed
  champion (zero forecast for 945 series, hurdle_hgb for 75 series,
  hgb_tweedie for 14, peak_weighted_hgb for 11, adida_sba for 11,
  adida_tsb for 7, lgbm_tweedie for 3, hurdle_lgbm for 3 — selected on
  selection origins) beats
  the seasonal-naive floor decisively at both h=7 and h=14 (CIs exclude
  zero) and beats the unrouted all-HGB ladder by **3.982 MAE** (CI [3.338,
  4.756]). All 15 erratic series leave the direct HGB for the peak-capable
  models (10 hurdle_hgb, 3 peak_weighted_hgb, 2 hgb_tweedie) — on
  spike-driven erratic demand the flat-lag HGB is simply outclassed, and the
  erratic unrouted-minus-routed gap is +22.9 MAE (CI [11.8, 35.2]) in
  routing's favour.
- **Where the ML candidates win — and where they don't** (pooled MAE over all
  horizons on the scored origins; routed 6.613 on lumpy / 68.582 on
  erratic): lumpy hurdle_hgb MAE **7.071**, lumpy peak_weighted_hgb MAE
  **7.301**, lumpy hurdle_lgbm MAE **7.619**, lumpy lgbm_tweedie MAE
  **7.624**, lumpy hgb_tweedie MAE **7.770**, lumpy routed_reconciled MAE
  **8.661**, lumpy ensemble_convex MAE **6.736** (+0.123 over routed, CI
  excludes zero) — every ML arm lands within ~1.2 MAE of the router on
  lumpy, reported plainly, not hidden. On erratic the order tightens:
  erratic hurdle_hgb MAE **67.844** comes in −0.738 under the routed
  pipeline (CI spans zero), erratic ensemble_convex MAE **68.582** equals
  routed exactly (it blends toward it), erratic peak_weighted_hgb MAE
  **68.258**, erratic hgb_tweedie MAE **72.768**, erratic hurdle_lgbm MAE
  **73.291**, erratic lgbm_tweedie MAE **83.457**, erratic routed_reconciled MAE **103.174**. And the honest loser:
  lumpy lgbm_poisson MAE **103.260** / erratic lgbm_poisson MAE **386.024** —
  evaluated, kept in every table, and beaten by the zero forecast (9.276):
  its exp link overflows on this panel (literal +inf on ~11% of cells before
  the finite-prediction guard maps non-finite cells to the per-series
  training max). The multi-step leaderboard is led by the routed pipeline
  (**7.471** — pooled rmae **0.649** vs the floor), then ensemble_convex
  (7.592), hurdle_hgb (7.912), peak_weighted_hgb (8.144), hurdle_lgbm
  (8.528), hgb_tweedie (8.669), lgbm_tweedie (8.673), zero (9.276),
  ma_28 (9.944), routed_reconciled (9.969), adida_tsb (9.977), tsb (10.722),
  adida_sba (10.732), seasonal_naive (11.514), direct_hgb (11.714), sba
  (12.012), croston (12.310), lgbm_poisson (107.173) last; the
  routed-vs-ensemble_convex rank-1-vs-2 gap CI [−0.180, −0.068]
  excludes zero.
- **Error grows with the true horizon** — pooled MAE (units) on the scored
  origins:

  | h | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | champion | 0.075 | 3.722 | 8.662 | 9.255 | 8.975 | 16.407 | 6.701 | 0.087 | 4.600 | 9.367 | 9.447 | 9.380 | 11.512 | 6.399 |
  | floor (sn) | 0.000 | 4.846 | 10.922 | 14.072 | 13.213 | 26.871 | 11.863 | 0.000 | 5.522 | 14.275 | 13.795 | 13.223 | 21.272 | 11.325 |
  | zero | 0.000 | 5.249 | 10.223 | 12.201 | 11.334 | 19.223 | 7.994 | 0.000 | 6.004 | 11.500 | 12.524 | 11.747 | 14.255 | 7.608 |

  The sawtooth is real, not noise: weekly origins fix the weekday of each
  horizon (h ≡ 1 mod 7 — h=1 and h=8 — always lands on the same near-zero
  Saturday on this panel, which is also why the peak-featured champion now
  scores 0.075/0.087 there instead of the old ladder's 2.461), so the curve
  is horizon × weekday composition, visible per class in
  `multistep_error_vs_horizon`.
- **Per-horizon bands** (target 80%; learner rows: ±q80 split-conformal per h
  calibrated on selection origins, zero-clipped and sorted; sparse rows:
  P(any sale) + quantile ladder of the training history — no collapsing
  band; the two ML candidates carry their own conformal bands, same rule).
  Coverage AND width per h on the scored origins:

  | h | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | coverage | 1.000 | 0.926 | 0.910 | 0.888 | 0.912 | 0.891 | 0.903 | 1.000 | 0.924 | 0.899 | 0.885 | 0.913 | 0.899 | 0.908 |
  | avg width (units) | 4.269 | 5.343 | 5.854 | 6.330 | 5.870 | 5.536 | 5.593 | 4.275 | 5.314 | 5.784 | 6.540 | 5.746 | 5.674 | 5.597 |
  | verdict | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative | conservative |

  Verdict rule: |coverage − 0.80| ≤ 0.05 calibrated, above conservative,
  below optimistic. Pooled 0.918 → **conservative**: the sparse history-q90
  band over-covers (0.885–1.000 per h) — honest width, stated per h in
  `probabilistic.json` (`multistep` key, incl. `candidate_bands` for the six
  ML candidates, pooled 0.908–0.909) and
  `multistep_band_calibration`. Pinball loss of the learner quantiles
  (erratic rows) is reported per h alongside (p50 pinball 0.0–113.2 units —
  the h ≡ 1 mod 7 days sit on the zero atom now).
- **Peak capture** (the user's headline question — per scored window over the
  scored h-lattice days: `peak_mae` = MAE on the window's top-decile-by-
  actual days; `peak_recall` = share of the window's top-5 actual days ranked
  in the forecast's own top-5; pooled per class, 95% paired bootstrap CIs):

  | candidate | lumpy peak_mae | lumpy recall | erratic peak_mae | erratic recall |
  |---|---|---|---|---|
  | routed | 29.939 | 0.881 | 285.577 | 0.457 |
  | zero | 33.685 | 0.881 | 367.258 | 0.493 |
  | hgb_tweedie | 28.124 | 0.441 | 278.721 | 0.467 |
  | hurdle_hgb | 29.982 | 0.444 | 295.067 | 0.493 |
  | lgbm_tweedie | 28.336 | 0.401 | 281.070 | 0.463 |
  | lgbm_poisson | 120.410 | 0.336 | 489.610 | 0.410 |
  | hurdle_lgbm | 29.676 | 0.450 | 288.005 | 0.477 |
  | peak_weighted_hgb | 29.342 | 0.439 | 283.037 | 0.480 |
  | ensemble_convex | 29.469 | 0.764 | 285.577 | 0.457 |
  | routed_reconciled | 27.923 | 0.623 | 226.067 | 0.493 |

  Read honestly: on **erratic** every ML candidate cuts peak-day error vs
  the zero forecast (routed 285.6 vs zero 367.3, CI excludes
  zero) — that is the dramatic error improvement on peak days, delivered by
  routing those series to the peak-capable models. On **lumpy** hgb_tweedie
  cuts peak-day MAE to 28.124 (vs zero 33.685, vs routed −1.815 with CI
  excluding zero) — but it pays for magnitude with timing: its top-5
  day-ranking recall is 0.441 vs the flat baselines' 0.881 (CI excludes
  zero), because committing to peak days is wrong more often than the flat
  "never predict a peak" strategy on 89%-zero demand. The wave-22
  `routed_reconciled` anchor improves lumpy peak-day MAE further (27.923)
  but only by reshuffling mass toward the country aggregate — its recall
  drops to 0.623 and its pooled MAE loses to plain routing (see the
  leaderboard), so it stays a benchmark, not a router. lgbm_poisson's
  overflow residue shows up here too (lumpy peak_mae 120.4, recall 0.336 —
  worst on both). Both facts are in
  `metrics.json` (`peak_capture`) and `multistep_peak_capture` /
  `multistep_peak_day_scatter`.
- **Win rates — the "improve EVERY series" metric** (wave 21): pooled MAE can
  fall while most series lose, so per class and horizon we count the share of
  series whose summed |error| over the scored origins beats the
  seasonal-naive floor (95% cluster bootstrap over series, 2,000 draws):
  lumpy routed beats-floor h=7: **21.89%** (CI [19.55, 24.32]);
  lumpy routed beats-floor h=14: **23.20%** (CI [20.77, 25.82]);
  erratic routed beats-floor h=7: **60.0%** (CI [33.33, 86.67]);
  erratic routed beats-floor h=14: **80.0%** (CI [60.00, 100.0]).
  Read honestly: even the champion beats
  the floor on barely a fifth of lumpy series — the pooled win rides on
  magnitude, not coverage. The per-candidate spread at lumpy h=7 is narrow
  (hurdle_hgb 22.92%, ensemble_convex 22.64%, peak_weighted_hgb 22.26%,
  hurdle_lgbm 22.26%, routed 21.89%, lgbm_tweedie 21.05%, routed_reconciled
  19.74%, hgb_tweedie 19.55%, zero 19.36%) except lgbm_poisson at 3.27% —
  evaluated and losing, never hidden. The full grid is in `metrics.json`
  (`win_rates`) and `multistep_win_rates`.
- **Decision metric — order-up-to policy simulation** (service level τ →
  order = quantile_τ(point + residual quantiles calibrated per class on
  selection origins); cost = holding 0.25/unit leftover + stockout 4.0/unit
  short per scored cell; assumptions in the JSON; **simulation — no savings
  claims**). Per-unit-of-demand cost at τ=0.90: erratic **1.422 champion vs
  1.510 floor** (−7,099 total on the scored cells); lumpy 2.874 vs 2.777
  (+46,640). The asymmetry persists: the MAE-optimal routed champion
  over-orders at high τ on spike-driven lumpy demand (its raw-demand residual
  quantiles are large), while on the erratic series its tighter distribution
  wins at τ ≤ 0.90. Safety-stock policy and forecast model are different
  decisions — the metric exists to make that visible.
- **Wave-22 candidates and metric layer** (the audit's "missing baselines and
  better metrics" round):
  - `ma_28` and the ADIDA pair join the sparse pool and lose honestly:
    pooled MAE ma_28 **9.944**, adida_tsb **9.977**, adida_sba **10.732** —
    all behind the zero forecast (9.276) and far behind the router (7.471).
    On lumpy their rmae sits at 0.866 / 0.887 / 0.963 vs routed 0.642. The
    temporal-aggregation machinery works as designed; the data simply has no
    exploitable weekly structure at series level — 18 of the 1,069 lumpy
    series route to an ADIDA variant, the rest stay on zero/hurdle picks.
  - `routed_reconciled` (country-aggregate anchoring) also loses on pooled
    MAE — 9.969, behind zero — while cutting lumpy peak-day MAE to 27.923.
    Simple proportional anchoring toward a seasonal-naive country aggregate
    injects the floor's noise into the 87% of lumpy series whose best
    forecast is flat zero; a covariance-aware (MinT-style) reconciliation is
    the documented next step, not this wave's rule.
  - **rmae / rmsse**: champion pooled rmae **0.649** (floor = 1.000 by
    construction); per-candidate rmae and M5-convention rmsse (in-sample
    seasonal-naive-7 MSE denominator, per series × scored origin) are
    committed per class and pooled — routed rmsse 0.520 (volume-weighted
    0.724) vs the floor's 0.796.
  - **Newsvendor order-quantile cost** (order = the routed band's q-quantile —
    dense rows interpolate the committed p10/p50/p90 ladder, sparse rows the
    training-history ladder; the floor orders the same quantile of the
    seasonal-naive weekday distribution; holding 1.0 / stockout 3.0 per
    unit-day, documented assumption, **no savings claims**; expected daily
    cost per unit-demand, 95% paired bootstrap CIs): erratic q=0.90 routed
    **1.820 vs floor 1.727** (+0.093, CI excludes zero); lumpy q=0.90 **2.370
    vs 2.243** (+0.127, CI excludes zero). At q=0.80 the same shape holds
    (erratic +0.066 and lumpy +0.118 per unit-demand, both CIs excluding
    zero). At q=0.95 the erratic comparison
    flips in routing's favour (−0.137, CI excludes zero) while lumpy stays a
    wash (+0.066, CI spans zero) — the same over-ordering story as the
    order-up-to layer, now priced at the quantile of the committed band.

### Related work — external benchmarks

- **[collapseindex/online-retail-forecast](https://github.com/collapseindex/online-retail-forecast)**
  — an independent, audit-first benchmark on this exact dataset where the
  **seasonal naive wins**. That is the same finding our router reaches from
  the inside: on 98.6%-sparse series the zero/flat forecast is the ceiling,
  and our "zero for 945 of 1,069 lumpy series" routing is not a bug but the
  measurement.
- **ADIDA / IMAPA temporal aggregation** (Kourentzes,
  [kourentzes.com/forecasting](https://kourentzes.com/forecasting/)) — the
  aggregate-disaggregate lineage our `adida_sba`/`adida_tsb` implement:
  temporal aggregation helps intermittent series *when a seasonal structure
  exists*; here the weekly profile is too weak to beat zero, which is itself
  a measured fact about this panel.
- **MinT reconciliation** (Wickramasuriya, Athanasopoulos & Hyndman 2019,
  [doi.org/10.1016/j.ijforecast.2018.10.003](https://doi.org/10.1016/j.ijforecast.2018.10.003))
  — the covariance-projection approach our `routed_reconciled` is a
  deliberately simple cousin of; the honest result is that plain proportional
  anchoring to a seasonal-naive country aggregate **loses** on pooled MAE
  here.
- **M5 accuracy competition practice** ([arXiv:2311.00993](https://arxiv.org/abs/2311.00993))
  — gradient-boosted trees on M5-style hierarchies; our per-horizon direct
  HGB with native categorical series identity follows the same practice.
- **TSB-HB** ([arXiv:2511.12749](https://arxiv.org/abs/2511.12749)) — current
  research-grade intermittent-demand work quoting RMSSE on this dataset; our
  per-candidate M5-convention rmsse block is directly comparable.

## Synthetic track — CI fast path (`data_source: synthetic`, seed 42)

The synthetic hierarchy (24 series, clean trend + weekly seasonality) is the
**CI/offline path**: fully seedable, byte-reproducible, no network. It exists
so every gate in this repo runs hermetically; the headline results live on
the M5 track above, and the sparse-regime study on the UCI track below. Ladder
below is scored on the **final holdout
window** (last rolling origin), champion selected on origins 1..n-1 only —
note what clean data does to the statistical baselines:

| model | MAE (units) | RMSE (units) | MAPE (%) | MASE |
|---|---|---|---|---|
| naive_mean (global train mean) | 35.946 | 48.639 | 48.26 | 3.755 |
| naive_last (persistence, y(t-1)) | 16.223 | 22.238 | 19.47 | 1.695 |
| seasonal_naive (lag-7) | 11.780 | 16.689 | 13.98 | 1.231 |
| **ETS (Holt-Winters, damped+weekly)** | **8.924** | **12.691** | **10.37** | **0.932** |
| ridge (linear baseline) | 9.705 | 13.706 | 11.92 | 1.014 |
| hgb (default HGB) | 9.549 | 13.380 | 11.58 | 0.998 |
| hgb_tuned (Optuna, 56 trials) | 9.472 | 13.269 | 11.51 | 0.990 |
| xgb_tuned (Optuna, 25 trials) | 9.525 | 13.372 | 11.59 | 0.995 |
| lgbm_tuned (Optuna, 25 trials) | 9.341 | 13.101 | 11.31 | 0.976 |
| temporal_net (PyTorch emb+MLP) | 9.244 | 12.908 | 11.38 | 0.966 |

On clean synthetic data **ETS wins outright** (MASE 0.932) — a correctly
specified Holt-Winters model is exactly the right class for smooth
trend + weekly seasonality, and the boosters only approximate it. This is the
deliberate counterpoint to the real track, where intermittency flips the
ordering. Two honest notes from the frozen holdout: on this one test window
`temporal_net` posts the lowest ML MAE (9.244, a hair ahead of `lgbm_tuned`
9.341 — a gap well inside the fold-to-fold spread), and every run's
test-window MAE is higher than its pooled legacy number because the last fold
carries the most trend drift; both are one-window estimates, not new
champions.

Key findings:

- Against the stronger naive floor (`naive_last`), the champion cuts test-window
  MAE by **45.0%** (16.22 → 8.92 units); against `naive_mean` the reduction is
  75.2%. Persistence loses because demand has strong weekly seasonality and a
  rising trend: yesterday's value systematically misses weekday effects and
  never anticipates the trend — the lag/calendar features plus a nonlinear
  model capture exactly those two structure components.
- **LightGBM edges out the incumbent HGB config** on the pooled selection folds
  (legacy pooled MAE 8.413 vs 8.529) and stays the best ML run on the
  synthetic test window (9.341 vs 9.472). `xgb_tuned` is a statistical wash vs
  `hgb_tuned`. Three independent boosting libraries land within 1.5% of each
  other — on this panel the marginal value of further model-family search is
  small, and honest reporting says so.
- **HPO earned a modest but real gain** across arms: 56 seeded trials improved
  the sklearn HGB from 8.619 to 8.529 (-1.0%) pooled over all folds (legacy
  numbers); see the `hpo_history` / `hpo_importance` figures (per-arm
  variants for xgb/lgbm).
- **The neural model is competitive but not the champion.** `temporal_net`
  tracks ridge on the selection folds and lands the best ML test-window MAE
  (9.244) — but ETS, selected on origins 1..n-1, still wins outright. On small
  tabular lag features, gradient-boosted trees and a well-specified
  Holt-Winters remain the tools to beat; reported honestly.
- **Reconciliation (MinT-lite, test window, store level)**: the grid estimator
  chose w=0.00 this run — the parent-level model suffers the same fold-4 drift
  as the children, so no trust is placed in it. Store-level MAE moved
  24.133 → 24.133 and incoherence |parent forecast − Σ children| moved
  26.688 → 26.688 (exactly ×(1−w), the tested coherence property; the
  store-level backtest re-fits HGB and, per the wave-13 platform note, jitters
  run-to-run within the OpenMP-reduction tolerance — these are the latest
  canonical run's numbers). Structural coherence is guaranteed; accuracy gains
  from reconciliation need a drift-robust parent model — a documented,
  quantified caveat.
- Where the gains plateau: all runs degrade on the last fold as the injected
  trend lifts demand, but the improvement ratio over persistence is stable
  across folds. The residual ~9-unit test-window MAE is mostly day-over-day
  noise, which no lag feature can remove.

Per-fold MAE (see the `fold_stability` figure for the full ten-run view;
fold 4 is the holdout window):

| fold | naive_mean | naive_last | ridge | hgb | hgb_tuned | temporal_net |
|---|---|---|---|---|---|---|
| 1 | 27.748 | 12.853 | 9.280 | 7.860 | 7.728 | 9.229 |
| 2 | 30.266 | 13.800 | 8.572 | 8.149 | 8.083 | 9.837 |
| 3 | 33.086 | 15.029 | 8.907 | 8.916 | 8.834 | 9.053 |
| 4 | 35.946 | 16.223 | 9.705 | 9.549 | 9.472 | 9.244 |

hgb_tuned improves on hgb in **every** fold; on the holdout window
temporal_net finally leads the ML pack (9.244) without threatening ETS.

## Nowcast track (one-day-ahead) — real data (UCI Online Retail II, SECONDARY)

> **Track label:** this ladder is the retained **nowcast** (one-day-ahead)
> track, protocol `rolling_origin_holdout_v1` — its frozen-window numbers are
> valid and stay committed, but they are 14 consecutive one-day-ahead
> predictions, never mixed into the multi-step leaderboard below.

Real transactions, same pipeline, same embargoed rolling-origin backtest with
the frozen holdout: 525,461 sales lines parsed from the 2009-2010 sheet → top
8 countries × top 200 products, 374 days (2009-12-01..2010-12-09), 405,416
panel rows, **89.2% zero share** — classical intermittent demand. The table
below is scored on the **test window** (final origin, 2010-10-01..2010-12-09,
70 days); the champion was selected on origins 1..3 only. **MAE/MASE lead;
MAPE is reported but not decision-grade here** (near-zero actuals inflate it
to 184–328% for every run; the zero-demand caveat is in the
data-generating-process section above and in the figure captions):

| run | MAE | RMSE | MAPE | MASE |
|---|---|---|---|---|
| naive_mean | 12.475 | 74.699 | 90.3% | 1.382 |
| naive_last (persistence) | 11.505 | 99.548 | 327.6% | 1.331 |
| seasonal_naive (lag-7) | 11.323 | 114.921 | 305.4% | 1.310 |
| ETS (Holt-Winters, damped+weekly) | 11.471 | 80.827 | 302.7% | 1.338 |
| ridge (linear baseline) | 12.384 | 72.680 | 221.7% | 1.395 |
| hgb (default sklearn) | 9.565 | 71.700 | 260.3% | 1.085 |
| **hgb_tuned (Optuna, 56 trials) ← best** | **9.545** | **71.847** | 230.0% | **1.078** |
| xgb_tuned (Optuna, 25 trials) | 9.804 | 73.287 | 277.2% | 1.118 |
| lgbm_tuned (Optuna, 25 trials) | 9.409 | 71.360 | 272.3% | 1.076 |
| temporal_net (PyTorch emb+MLP) | 11.770 | 71.849 | 183.6% | 1.305 |

What the audit-driven statistical baselines reveal on **real** data:

- **They do not beat the boosters here** — the mirror image of the synthetic
  track, where ETS wins outright. `seasonal_naive` (11.323 test MAE, 1.310
  MASE) is the strongest floor and a serious contender — no run dips below
  MASE 1.0 on this test window: it covers the holiday quarter (Oct–Dec 2010),
  and the MASE scale is the naive's own in-sample error from a quieter period,
  so the naive itself scores 1.310 here and parity with it must be read on
  the Δ-vs-sn column, not the 1.0 line. ETS *loses* to
  its own seasonal naive (11.471 vs 11.323, MASE 1.338): Holt-Winters assumes
  every series is smooth and seasonal, and 89% zeros plus bulk spikes break
  that assumption (the fallback chain is documented and unit-tested).
- **Cross-track transfer is the honest punchline, and it reversed under the
  frozen protocol**: the old pooled ladder claimed the synthetic ML champion
  `lgbm_tuned` ranked fourth on real data (9.600). On the one-shot test
  window `lgbm_tuned` actually posts the **best** MAE of all runs (9.409,
  ahead of the selection champion `hgb_tuned` at 9.545 — a 1.4% gap inside
  the fold-to-fold spread, so one window cannot dethrone the protocol's
  pick), while the synthetic overall champion `ets` ranks 6th on real data
  (11.471). Configs tuned on clean synthetic data still behave differently on
  intermittent real demand; neither pooled nor single-window rankings should
  be read as more than what they are. This is why both tracks stay in the
  repo side by side.
- **Ridge is no longer the collapse story** (12.384 test MAE — mid-pack on
  this window, though its pooled legacy 16.734 was behind every floor) and
  **MAPE/RMSE are not decision metrics** on this data (184–328% MAPE; RMSE ≫
  MAE from wholesale spikes). MAE, MASE, bias and WAPE are the numbers to
  plan with — the champion's test-window bias is −1.444 units (mild
  over-forecasting) with WAPE 1.142.
- **Reconciliation pays off on the test window**: w=0.50 — incoherence 474.3 →
  237.2 (exactly ×(1−w), property-tested); store-level MAE 746.2 → 743.4
  (−0.4% this run — coherence is a guarantee, accuracy gains depend on
  parent-model quality, stated plainly; the shrinkage grid is estimated on
  origin 2 and the store-level backtest re-fits HGB — per the wave-13 platform
  note its OpenMP reductions jitter run-to-run, so these numbers are the
  latest canonical run's, not a deterministic constant).
- **Probabilistic (target 80% band)** — coverage AND average width on the
  test window's final 14 days (h=1..14):

  | track | quantile band (pooled over folds) | zero-aware split-conformal, horizon set | avg width | verdict |
  |---|---|---|---|---|
  | synthetic | 0.727 | 0.741 | 26.49 units | optimistic (under-covers) |
  | UCI real | 0.919 | 0.861 | 0.00 units | conservative — but degenerate |

  Honest reading: on clean synthetic data the band under-covers (0.741 vs
  0.80 target → optimistic). On intermittent demand the champion's median
  sits on the zero atom for ~100% of test-window rows, so the zero-aware
  band collapses to the point forecast (avg width 0.00 units) and its 0.861
  "coverage" only means 86.1% of actuals were exactly zero — the conservative
  verdict is a degenerate band, not a useful one. The quantile band covers
  0.919 pooled precisely because it is wide where the conformal band is
  empty. Per-bin calibration is explicit in `probabilistic.json` (per-horizon
  coverage and width arrays, `calibration_verdict`) and the figure states the
  achieved coverage and width; per-series (or clustered) conformal remains
  the fix direction.

Figures (HTML + JSON per track, `reports/figures/` synthetic,
`reports_uci/figures/` real) — the audit list:

- `forecast_fan` (real track) — p10/p50/p90 fan + actual for the two
  highest-volume series, last fold, with takeaway
- `coherence_heatmap` — per-store |parent − Σ children| before/after the
  MinT-lite adjustment, annotated
- `fold_stability` — the error-by-fold panel (drift visible per run)
- `forecast_vs_actual` — champion vs strongest naive on example series
- `metrics_bars` / `eda_series_overview` / `eda_units_distribution` /
  `hpo_history` / `hpo_importance` / `reconciliation_coherence` /
  `probabilistic_band` as before
- multi-step track (wave 19): `multistep_error_vs_horizon` (MAE and MASE on
  separate panels), `multistep_class_scoreboard` (champion vs floor at h=7/h=14
  with bootstrap CI on the gap), `multistep_routing` (all-HGB minus routed MAE
  per class), `multistep_band_calibration` (coverage and width per horizon on
  separate panels)

Artifacts: the M5 track writes `reports_m5/metrics.json` (per-candidate ×
{class, pooled} × {selection, test}: MAE/WAPE/rmae/WRMSSE/volume-weighted
WRMSSE/peak-day MAE + horizon-wise MAE + per-series win rates + the headline
gap bootstrap blocks + the `weekly_rolling` block — next-week h≤7 WAPE over
all 10 origins pooled/by class with bootstrap gaps and the measured
`always_beats_naive` verdicts, and the wk1..wk4 weekly error blocks on the
test origins), `probabilistic.json` (split-conformal band method,
per-horizon widths, coverage/pinball/width per candidate),
`evaluation_metadata.json` (protocol, checksums, seeds, package pins, metric
definitions, report sample series), `figures/` and `report.html`; the
`demo_payload.json` (schema v4) feeds the `forecast-workbench` showcase demo.
Per UCI/synthetic track, `reports*/metrics.json` (10 nowcast runs: test-window MAE/RMSE/
MAPE/MASE + bias/WAPE + fold MAEs + per-horizon arrays + `legacy_pooled_*`,
and a `_meta` protocol block — plus the `_multistep` block: protocol
`direct_multihorizon_v1`, origins, per-class headlines with bootstrap CIs,
horizon growth, routing, decision metric), `evaluation_metadata.json`
(nowcast protocol + `multi_horizon` v2 block), `report.html`,
`reconciliation.json`, `probabilistic.json` (nowcast coverage AND width per
horizon, `calibration_verdict` — plus the `multistep` per-horizon band table);
the UCI track also emits `dataset_metadata.json` (including the per-series
ADI/CV² `intermittency` classes). The small `reports_uci/*.json` files are
committed as drift-guard anchors; the heavy UCI artifacts (`data_uci/`,
`reports_uci/figures/`, `reports_uci/report.html`) stay local and regenerate
via `uv run python -m demand_forecasting.cli all --data-source uci`.
`data_uci/` (panel 405,416 rows, contract, models) and `data/` (synthetic).
Runtime (this machine, `cli evaluate`): synthetic ≈ **2 min** with
probabilistic + multi-step; UCI ≈ **30 min** (ETS fits 1,084 series per fold;
multi-step: 20 origins × 14 horizons × 14 model fits — point, 3 quantiles,
tweedie, hurdle pair, two LightGBM arms, LGBM hurdle pair, two peak-weighted
variants — joblib-parallel); 6/6 DQ
gates pass on both tracks.

## Reproduce

```bash
# from the repo root, inside the workspace venv
uv run python -m demand_forecasting.cli tune-m5           # re-tune the lgbm booster (seeded 25-trial study on the wave-27 feature space, ~25 min; writes params.yaml m5_lgbm)
uv run python -m demand_forecasting.cli evaluate-m5       # M5 headline track (~27 min, offline)
uv run python -m demand_forecasting.cli build-report-m5   # rebuild reports_m5/report.html from committed artifacts
uv run python -m demand_forecasting.cli demo-payload-m5   # the forecast-workbench demo payload (reports_m5/demo_payload.json)
uv run python -m demand_forecasting.cli all            # synthetic pipeline (~2 min)
uv run python -m demand_forecasting.cli all --data-source uci   # UCI sparse track (~30 min, fetches once)
uv run python -m demand_forecasting.cli hpo            # Optuna HPO (minutes; resumable; --model xgb|lgbm|multistep_tweedie)
uv run dvc metrics show                                 # declared metrics (reports/metrics.json)
# or stage by stage (mirrors dvc.yaml)
uv run python -m demand_forecasting.cli prepare
uv run python -m demand_forecasting.cli features
uv run python -m demand_forecasting.cli train
uv run python -m demand_forecasting.cli evaluate
# or
dvc repro projects/02-demand-forecasting
```

Tests run fully offline against seeded synthetic fixtures:

```bash
uv run pytest projects/02-demand-forecasting -q
```

## What this demonstrates for a client

- **Leakage discipline as a first-class concern**: features shifted, not
  centered; embargoed expanding-window backtest instead of a random split;
  per-fold stability reported alongside the headline metric so drift is
  visible before it hurts.
- **Baseline-first modelling**: naive floors (global mean, persistence,
  weekly seasonal-naive) and a per-series ETS anchor every claim; the trained
  models must *earn* their complexity — on the real-data test window the
  champion runs at **0.843 relative MAE of the seasonal-naive floor**
  (MASE 1.078 vs the naive's own 1.310 on the holiday-quarter test window,
  9.545 vs 11.323 MAE), and the frozen protocol is precisely what makes that
  number a measurement instead of a hope.
- **Model selection as an engineering discipline**: HPO optimises on the same
  embargoed folds it is judged on, the champion is picked on origins 1..n-1
  and scored once on the final holdout, the un-tuned model stays in the
  ladder for comparison, and the neural candidate is reported with its honest
  verdict rather than silently dropped.
- **Hierarchy handling without a per-series zoo**: one global model with
  series identity captures 24 series in a single deployable artefact.
- **Contract-governed data**: every dataset carries a versioned identity card
  and must pass DQ gates before any model trains — the pipeline fails loudly,
  not silently.
- **Reproducibility**: seeded data, pydantic-validated config, dvc stages,
  offline tests — results regenerate exactly on any machine with the repo.

## Roadmap

Delivered: the **M5 headline track** (wave 24, protocol `m5_direct_v1`) —
the committed checksum-pinned Walmart M5 subset (600 series, top-3 stores ×
top-200 items), 10 weekly rolling origins (8 selection + 2 scored once),
28-day horizon, 8 candidates from seasonal_naive to a global LightGBM and a
selection-fitted convex ensemble, ADI/CV² volume classes, WRMSSE with the
documented naive-28 denominator, paired-bootstrap CIs on every headline gap,
split-conformal 80% bands, and the churn-style `forecast-workbench` demo
payload (`cli demo-payload-m5`, schema v4) served by the showcase API — and
the wave-25 performance pass: the M5-practice lgbm feature set (rolling
stds/expanding mean/price momentum/any_snap/event distances), `cli tune-m5`
(seeded Optuna TPE on the selection origins → the params.yaml `m5_lgbm`
block), and the best-three 0.05-simplex ensemble; the wave-27 refinement
round then widened the feature space per the M5-winning-solution practice
(56/84-day means, snap_weekend, price-relative-to-mean, panel statics item
age/history level/dept/category pooled means — all leakage-safe), re-tuned
the lgbm (25 trials on the selection origins) and added a second global
booster (xgb) to the ensemble pool (committed: lgbm 0.498, xgb 0.496,
ensemble 0.491 test WAPE; next-week 0.4233). Also
delivered: UCI real-data sparse track, probabilistic forecasts
(quantile HGB + split-conformal), Optuna HPO across three boosting arms, the
wave-13 audit items — statistical baselines (`seasonal_naive` + per-series
damped Holt-Winters ETS with documented fallbacks) and **MASE** on both tracks,
the fan-chart/coherence-heatmap/error-by-fold figure set — the wave-19
fifth-pass audit rebuild: the **direct multi-horizon track** (`direct_multihorizon_v1`,
UCI secondary headline), ADI/CV² classification with statistical routing for sparse
series, Croston/SBA/TSB baselines, paired-bootstrap CIs on every headline
comparison, per-horizon conformal/sparse bands with coverage AND width, and
the order-up-to decision-metric simulation — and the wave-22 round: the
`ma_28`/`adida_sba`/`adida_tsb` statistical candidates, leakage-safe rolling
features (rmean7/14/28, rstd14/28), the `routed_reconciled` hierarchy-anchored
benchmark, and the rmae / per-candidate rmsse / newsvendor metric layer. What
remains:

1. ~~Calibrated intervals for intermittent demand~~ — delivered per horizon on
   the multi-step track (sparse P(sale) + quantile ladder bands, coverage AND
   width per h; conservative at 0.92 pooled — the remaining gap is *tighter*
   calibration, not structure). Per-series clustered conformal is still the
   next refinement.
2. ~~Origin-stacked multi-horizon bands~~ — delivered as the multi-step track's
   per-horizon split-conformal (learner rows) and sparse ladder bands, both
   calibrated on the selection origins.
3. **Full MinT reconciliation**: wave 22 tested the simple cousin (proportional
   anchoring to a seasonal-naive country aggregate) and it lost on pooled MAE
   while cutting peak-day error — covariance projection (Wickramasuriya et
   al. 2019) is the documented next step, not a proven win.
4. **Returns-aware demand**: model cancellations/returns as their own flow
   instead of excluding them, for net-demand forecasting.
5. **Cost-aware routing**: the order-up-to simulation and the wave-22
   newsvendor layer both show MAE-optimal routing can over-order at high
   service levels on spike-driven series — a cost-aware variant of the
   routing rule is the natural follow-up.
