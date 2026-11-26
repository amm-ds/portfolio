# 02 · Demand Forecasting

**Domain:** time-series forecasting · **Data:** Walmart M5 accuracy
competition, full panel (30,490 daily store-item series, 2011-01-29..2016-06-19,
47,649,940 rows) · **Status:** working showcase on the standard platform
(flagships: [01](../01-rag-agent), [07](../07-open-data-mobility))

## Problem

A retailer needs **per-store-product daily unit forecasts** it can trust for
replenishment, not on a convenient sample of the catalog, but on the full
panel, where most series sell nothing on most days. The project runs the
Walmart M5 accuracy competition end to end at its real scale and grades every
candidate under the **official hierarchical WRMSSE**: the revenue-weighted
error across all 42,840 nodes of the store-category-item hierarchy. Either
scale invalidates a random train/test split: dated panels leak the future into
the past and overstate accuracy, so the evaluation runs embargoed rolling
origins with a frozen, scored-once test window, the last 28 days of the panel,
the competition window itself. The deliverable is a reproducible pipeline that
validates its data, engineers leakage-safe features, and compares a naive
floor against global, pooled, and statistical models under that protocol.

## Design

See [DESIGN.md](DESIGN.md) for the full requirements/options/decisions log.
Summary:

- **Data** (`m5_data.py`/`m5_full.py`, protocol `m5_full_v1`): the committed,
  checksum-pinned Walmart M5 **full panel**. 30,490 daily store-item series
  (10 stores × 3,049 items), 1,969 days, 59.5% zero-demand days, built offline
  from the Nixtla `datasetsforecast` mirror of the competition archive (sha256
  pins in `data_m5/`, provenance in `data_m5/raw/PROVENANCE.md`). The hierarchy
  aggregates the bottom series bottom-up through 12 levels (42,840 nodes).
- **Features** (`m5_track.py`): the committed feature space, lags
  1/7/14/21/28, rolling means 7/28/56/84 and rolling stds 7/28 at lag 1,
  rolling mean 7/28 and std 7 at lag 7, an expanding mean, calendar
  day-of-week/day/month, and exogenous price/SNAP/event codes, all built with
  `shift` per series (never the current row); undefined-lag rows are dropped,
  never imputed.
- **Candidates** (`m5_full.py`): eight arms, the seasonal-naive floor; a
  global LightGBM over all 30,490 series (mlforecast recursive, tuned
  committed config, seed 42); a Tweedie-loss twin; three pooled-global fits
  (one per store, per store×category cell, per department); per-series AutoETS
  (statsforecast); and a stability-screened convex ensemble of the pool.
- **Selection** (`m5_full.py`): the stability screen, best three of the pool by
  mean + 1.0×population std of the per-origin official WRMSSE over the
  selection origins; simplex-grid weights (step 0.05) minimising the same
  screen; computed exactly from the forecast-level blend re-aggregated through
  the hierarchy. Selection never reads the test origin.
- **Validation** (`m5_full.py`): 10 weekly rolling origins (9 selection +
  the last used for the champion's test headline), 28-day horizon, ≥ 1,096 training days; the
  official hierarchical WRMSSE (per-node RMSSE vs the node's train volatility,
  revenue weights with equal total per level, zero-scale nodes excluded and
  counted) plus bottom WAPE, bias, stability, per-level WRMSSE, and zero-day
  accuracy. The machine-readable protocol is
  [reports_m5_full/evaluation_metadata.json](reports_m5_full/evaluation_metadata.json);
  the written report is `reports_m5_full/report.html`.

## M5 headline: Walmart M5 FULL panel (protocol `m5_full_v1`, PRIMARY)

The headline experiment is the committed Walmart M5 **full panel**. 30,490
daily store-item series across 1,969 days, 2011-01-29..2016-06-19 (47,649,940
rows, 59.5%
zero-demand days), scored under the official hierarchical WRMSSE over all
42,840 revenue-weighted nodes. Protocol: **10 weekly rolling origins**
(9 SELECTION + the last scored once as TEST: 2016-05-22, the competition
window), each training on ≥ 1,096 days and scoring the next **28 days** (the
M5 evaluation horizon). Candidates: per-series statistical floor
(`seasonal_naive`), a global **LightGBM** and a **Tweedie-loss** twin
(mlforecast 1.1.0 recursive over the committed feature space: lags
1/7/14/21/28, rolling means 7/28/56/84 and stds 7/28 at lag 1, rolling mean
7/28 and std 7 at lag 7, expanding mean, calendar day-of-week/day/month,
exogenous price/SNAP/event codes), three **pooled-global** LightGBM variants —
one fit per store
(`lgbm_pool_store`, 10 groups), one per store×category (`lgbm_pool_storecat`,
30 groups), one per department (`lgbm_pool_dept`, 7 groups), three complementary
related-series groupings, per-series **AutoETS**
(statsforecast 2.1.1, season 7), and the **convex_ensemble** of the best
three pool members by the stability screen (weights grid-fit on a 0.05
simplex over the selection origins only, never reading test).

Volume classes per series: Syntetos-Boylan ADI/CV² on each series' real
history up to the last selection origin. **2,754 dense + 27,736
intermittent** (91% of the panel). Nothing reads the test origin at
fit/selection time; every fit is seeded or closed-form, so a re-run reproduces
the artifacts byte-for-byte.

Headline table, official hierarchical WRMSSE on the scored-once test origin
(42,840 revenue-weighted nodes; vs floor = relative cut; stability =
population std of the per-origin official WRMSSE over the 9 selection
origins):

| candidate | official WRMSSE | vs floor | bottom WAPE | bias | stability |
|---|---|---|---|---|---|
| **convex_ensemble (champion)** | **0.6211**¹ | **−30.4%** | **0.7623** | **+0.0222** | **0.0538** |
| lgbm_pool_store (best single) | 0.6219 | −30.3% | 0.7617 | +0.0177 | **0.0549** |
| lgbm_pool_storecat | 0.6225 | −30.3% | 0.7626 | +0.0228 | 0.0540 |
| lgbm_pool_dept | 0.6459 | −27.7% | 0.7615 | +0.0116 | 0.0470 |
| lgbm_tweedie | 0.6473 | −27.5% | 0.7642 | +0.0122 | 0.0555 |
| lgbm | 0.6601 | −26.1% | 0.7626 | +0.0041 | 0.0347 |
| auto_ets | 0.7093 | −20.6% | 0.7710 | −0.0063 | 0.0525 |
| seasonal_naive (floor) | 0.8929 | — | 0.9159 | −0.0120 | 0.0577 |

¹ **One scored test origin.** 0.6211 is a single evaluation on the final 28
days. A seeded node bootstrap over the 42,840 hierarchy nodes (2,000
resamples, `reports_m5_full/headline_interval.json`) bounds the blend level
at [0.5588, 0.6974]; the ensemble–floor gap itself still carries no paired
uncertainty bound.

The demo curves show the scored 0.6211 blend (weights 0.95/0.00/0.05, chosen on 9 selection origins). They previously carried an earlier 0.6161 blend with weights 0.60/0.10/0.30 from a run whose weights were chosen on 2 selection origins; both were scored once on the same test origin, 2016-05-22, at 0.6161 and 0.6211 WRMSSE respectively. The pass-4 E9 refit regenerated the catalog, demo payload, and sample-series figure on the current champion, reproducing the committed member and blend scores to under 1e-6.

- **The committed comparison is the seasonal-naive floor**: the convex
  ensemble lands at **0.6211**, a **−30.4%** cut over the floor's 0.8929,
  scored once on the final 28 days under the official revenue-weighted scheme
  across all 42,840 nodes. This is not a leaderboard or competition-winner
  comparison: no equivalent external run is evaluated by this project. Protocol
  reference: [Makridakis et al., IJF 2022](https://doi.org/10.1016/j.ijforecast.2021.11.013).
- **Pooled direct fits beat the recursive global fit at full scale.** All three
  pooled arms (0.6219 / 0.6225 / 0.6459) land ahead of the global model
  (0.6601), but this comparison changes both grouping and forecasting strategy;
  it does not isolate pooling as the cause. This reverses the subset-era finding
  (600 dense, top-volume series), where pooling starved each fit.
- **The ensemble's edge over the best single is marginal.** The blend scores
  0.6211 against 0.6219, while the single fit has slightly better bottom WAPE
  (0.7617 vs 0.7623) and bias (+0.0177 vs +0.0222). The blend's zero weight on
  `lgbm_pool_store` leaves a 95/5 mix of two active fits.
- **The Tweedie arm and AutoETS, stated as measured.** The Tweedie-loss twin
  posts 0.6473, ahead of the global model, behind the pooled arms. AutoETS
  clears the floor comfortably (0.7093 vs 0.8929) but trails every boosting arm.
- **Relative and absolute gains differ by level.** Total falls from 0.5600 to
  0.3143 (43.9%), the largest relative cut; item-store has the largest absolute
  gap at about 0.341.
- **Intermittency is priced in, not solved.** 91% of series are intermittent
  and 59.5% of panel days are zero. On zero-actual days the ensemble is right
  57.2% of the time against the floor's 66.6%.

The ensemble composition: **lgbm_pool_storecat × 0.95 + lgbm_pool_store ×
0.00 + lgbm_pool_dept × 0.05**, the best three of the six-candidate pool by
the stability screen (mean + 1.0×std of the per-origin official WRMSSE over
the 9 selection origins), weights on a 0.05 simplex grid minimising the same
screen, computed exactly from the forecast-level blend re-aggregated through
the hierarchy.

Stated limits: the selection screen is thin (9 selection origins, a protocol
limit, not a tight selection bound); the headline gap has no paired bootstrap
CI (the blend level's node-bootstrap interval is footnoted above), although
the separate spike-capture regression does; the demo band is the per-day
min/max envelope of the
blend members, not a calibrated prediction interval; neural global models
(N-HiTS, TFT, Chronos-class) are not benchmarked; stockouts, promotions, and
returns are unmodeled, so no savings or safety-stock claim follows.

### Related work: M5 and the forecasting stack

- **M5 competition companion** (Makridakis et al., *International Journal of
  Forecasting*, 2022, [DOI](https://doi.org/10.1016/j.ijforecast.2021.11.013)) —
  the competition this panel comes from. This track
  follows the official evaluation: the full 30,490-series bottom panel, the
  12-level hierarchy (42,840 nodes), revenue weights with equal total per
  level, and the final 28-day window scored once.
- **The nixtla stack** ([nixtla.github.io](https://nixtla.github.io)) —
  statsforecast / mlforecast / datasetsforecast power every candidate here;
  the per-series statistical layer and the global LightGBM recursive strategy
  follow their documented patterns (pinned versions in
  evaluation_metadata.json).
- **A Kaggle-competitions analysis of the M5 accuracy round**
  ([arXiv:2009.07701](https://arxiv.org/abs/2009.07701)), background on the
  candidate families; it is not used as an external performance comparison.

## Data-generating process (M5 panel)

`data_m5/raw/PROVENANCE.md` is the machine-readable provenance anchor: the
competition archive (via the Nixtla `datasetsforecast` mirror, sha256-pinned),
the calendar/sales/pricing join, the 30,490-series bottom panel (10 stores ×
3,049 items), and the 12-level aggregation tree. The daily panel keeps one row
per (day, item, store) with units sold, sell price, SNAP and event flags; the
59.5% zero share is real demand signal (slow movers, not missing data, the
competition calendar marks closed days separately). Everything else the
pipeline needs, the tuned booster config (`params.yaml`, `m5_lgbm` block),
the class thresholds, the metric definitions, is committed next to the
artifacts in `reports_m5_full/`.

## Artifacts

The full track writes `reports_m5_full/metrics.json` (per-candidate × origin:
official WRMSSE, bottom WAPE, bias, stability, zero-day accuracy, per-level
WRMSSE + the ensemble screen/members/weights), `evaluation_metadata.json`
(protocol, checksums, seeds, package pins, runtime), `report.html`
(self-contained interactive report), `figures/` (per-level, pooling-panel, and
ranked-candidate charts), and the catalog pair
(`catalog_forecasts.parquet` + `catalog_meta.json`: every candidate re-fit at
the test origin for a deterministic 48-series curated catalog, feeding the
`forecast-workbench` demo via `demo_payload.json`, schema v4). The subset-era
`reports_m5/` artifacts stay on disk as CI anchors but are no longer the
presented surface; the UCI/synthetic tracks' files likewise remain for the
test-suite and regenerate with `cli all --data-source uci` / `cli all`.

## Limits

The headline is one scored-once competition window on one (full-scale) panel —
no claim of transfer to other hierarchies or calendars. The seasonal-naive
floor still wins the quiet days, and the catalog refits exist to serve
the demo, not to generalize beyond the committed window.

## Reproduce

```bash
# from the repo root, inside the workspace venv
uv run python -m demand_forecasting.cli evaluate-m5-full        # the full-panel headline (extended, offline, checksum-pinned)
uv run python -m demand_forecasting.cli build-report-m5-full    # rebuild reports_m5_full/report.html from committed artifacts
uv run python -m demand_forecasting.cli build-figures-m5-full   # rebuild reports_m5_full/figures/ from committed artifacts
uv run python -m demand_forecasting.cli demo-payload-m5-full    # the forecast-workbench payload (reports_m5_full/demo_payload.json)
uv run dvc repro projects/02-demand-forecasting                 # or: the dvc pipeline
```

Tests run fully offline against seeded synthetic fixtures plus the committed
full-panel drift guards:

```bash
uv run pytest projects/02-demand-forecasting -q
```

## Common errors

| symptom | cause | fix |
|---|---|---|
| `evaluate-m5-full` runs for hours | the full-panel headline is a **extended** overnight run by design | scope a re-run with `--series-cap 2000` (~90 min catalog pass), or use the offline pytest suite above for a smoke check |

## What this demonstrates for a client

- **Leakage discipline as a first-class concern**: features shifted, not
  centered; dated rolling origins instead of a random split; the champion's
  final 28-day headline is separate from selection, with the later challenger
  gate's second test read explicitly disclosed.
- **Full-scale honesty**: the evaluation runs on all 30,490 series, 91% of
  them intermittent, under the competition's own 42,840-node metric, no
  top-volume subset silently flattering the models.
- **Baseline-first modelling**: the seasonal-naive floor anchors every claim,
  and the results say where it still wins (quiet days) as plainly as where it
  loses (the hierarchy).
- **Model selection as an engineering discipline**: the ensemble is chosen by
  a stability screen on selection origins only and compared with the committed
  seasonal-naive floor, without an unsupported leaderboard-equivalence claim.
- **Reproducibility**: seeded data, checksum-pinned inputs, closed-form or
  seeded fits, dvc stages, offline tests, results regenerate byte-for-byte on
  any machine with the repo.
