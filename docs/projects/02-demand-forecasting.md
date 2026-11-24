# 02 · Demand Forecasting

**Domain:** time-series forecasting · **Data:** Walmart M5 accuracy track at
full scale (30,490 daily store-item series) · **Status:** working showcase on
the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

> M5 full panel: 30,490 series, one scored test origin (final 28 days) with official 42,840-node WRMSSE. Pooled LightGBM ensemble: 0.6211 vs seasonal-naive 0.8929 (−30.4%); no bootstrap interval bounds the result; quiet days favor the floor.

[Case study source and interactive figures on GitHub →](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting)

## What it shows

Production-depth demand forecasting measured with the official M5 metric.
Global and multi-level pooled LightGBM fits (per store, per store×category,
and per department), a
Tweedie-loss variant for skewed intermittent demand, per-series AutoETS, and a
seasonal-naive floor, combined by a stability-screened convex ensemble and
scored through the full 12-level, 42,840-node hierarchy with revenue weights.
Everything is reproducible from sha-pinned data: one command, deterministic;
the committed 10-origin run logged about 1.35M seconds.

## Protocol (`m5_full_v1`, committed `reports_m5_full/`)

The full bottom-level panel (30,490 series × 1,969 days, 2011-01-29..2016-06-19,
zero share 59.5%) is evaluated over 10 weekly rolling origins (7-day spacing,
min 1,096 days of history), forecasting 28 days. The first nine origins select
the ensemble (stability screen: mean + 1.0 × population std of per-origin
official WRMSSE); the last origin — the literal M5 competition window
(2016-05-23..2016-06-19) — is scored once. The machine-readable record is
`reports_m5_full/evaluation_metadata.json`; hierarchy nodes derive from the
panel's own item/department/category/store/state structure (42,840 nodes), and
level weights are the preceding 28 days' revenue — the official scheme.

## Key results — official hierarchical WRMSSE on the competition window

Lower is better; weights are revenue-based across all 42,840 nodes.

| candidate | official WRMSSE | vs floor |
|---|---|---|
| seasonal_naive (floor) | 0.8929 | — |
| auto_ets | 0.7093 | −20.6% |
| lgbm (global) | 0.6601 | −26.1% |
| lgbm_tweedie | 0.6473 | −27.5% |
| lgbm_pool_storecat | 0.6225 | −30.3% |
| lgbm_pool_store | 0.6219 | −30.3% |
| lgbm_pool_dept | 0.6459 | −27.7% |
| **convex_ensemble (champion)** | **0.6211** | **−30.4%** |

Ensemble composition (selection screen, test never consulted): lgbm_pool_storecat
× 0.95 + lgbm_pool_store × 0.00 + lgbm_pool_dept × 0.05.

- **The internal baseline is the supported comparison** — the ensemble improves
  −30.4% over the seasonal-naive floor on the same full hierarchy and scored-once
  window. No competition-winner or leaderboard equivalence is claimed.
- **Pooling wins at full scale** — all three pooled fits beat the single global
  model (0.6219–0.6459 vs 0.6601) in this committed run; the 600-series subset
  measured the opposite, which is why the conclusion is stated at full scale only.
- **The hierarchy is the hard part** — the ensemble's biggest edge sits at the
  aggregate levels (total 0.314 vs floor 0.560; store level 0.461 vs 0.718);
  at the item×store leaves every learned candidate lands at 1.04–1.15 while the
  floor scores 1.38–1.39: intermittent leaves stay noisy for everyone.
- **91% of the panel is intermittent** (27,736 of 30,490 series by ADI/CV²) —
  on zero-actual days the naive floor still wins (66.6% vs 57.2% accuracy);
  full scale prices that in instead of solving it.
- **Stated limits** — the selection screen runs on nine origins and the headline
  has no bootstrap confidence interval. The demo envelope is member spread, not
  a calibrated interval; neural global models (N-HiTS/TFT/foundation) are not
  benchmarked, and stockouts, promotions, and returns remain unmodeled.

## Artifacts

- Metrics + protocol: `reports_m5_full/metrics.json` · `evaluation_metadata.json`
- Full evaluation report (embedded interactive figures):
  `reports_m5_full/report.html` — also served by the showcase API at
  `/projects/02-demand-forecasting/report`
- Interactive figure payloads: `reports_m5_full/figures/`
- Live-demo payload: `reports_m5_full/demo_payload.json` (schema v4,
  forecast-workbench)
- Demo catalog: `reports_m5_full/catalog_forecasts.parquet` (48 series — 24
  top-volume + 24 hardest-intermittent, balanced across store/category cells)
  with `catalog_meta.json`
- Data: full panel sha-pinned in `data_m5/` (PROVENANCE.md, Nixtla
  `datasetsforecast` mirror); story: `story.yaml`

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/README.md) —
  design summary, final numbers, reproduce commands
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/02-demand-forecasting/DESIGN.md) —
  requirements, options considered, protocol decisions, changelog
- Dataset card: [Walmart M5 (Nixtla mirror)](../data-registry/m5-nixtla-mirror.md) — if absent, see PROVENANCE.md
- Drift response runbook: [drift-response.md](../runbooks/drift-response.md)
- Source: `projects/02-demand-forecasting/src/demand_forecasting/`
