// GENERATED — do not edit.
// Map of project id → story.yaml `short_version`, baked by
// scripts/gen_story_short.py (same loader the showcase API uses). This is the
// single plain-text source for card/SEO/social short copy
// (portfolio_core.story.ProjectStory.short_version); lib/impact.ts reads it.
// README/docs copies are checked by scripts/check_short_copy.py, not written here.
// Re-run that script after changing any story.yaml; a re-run without changes
// produces byte-identical output.

export const STORY_SHORT: Record<string, string | null> = {
  "01-rag-agent": "Cited question answering over 593 Wikipedia articles. Hybrid search finds a correct passage in the top five 94.6% of the time (recall@5 0.946). Final 120-question test: F1 0.9091, precision 0.952, one unsupported answer. The judge agreed with all 30 hand-labelled checks.",
  "02-demand-forecasting": "M5 full panel: 30,490 series, one scored test origin (final 28 days) with official 42,840-node WRMSSE. Pooled LightGBM ensemble: 0.6211 vs seasonal-naive 0.8929 (−30.4%); no bootstrap interval bounds the result; quiet days favor the floor.",
  "03-anomaly-detection": "On 9 NAB series, IsolationForest touches 16 of 17 incidents but fires 1,609 alerts. Merging bursts and a per-series daily page cap cut it to 80 pages. Averaging three detectors halves 66 pages to 35 at equal recall (0.604). NAB standard-profile score 51.45 (null 0, perfect 100).",
  "04-nlp-classification": "AG News sorter: the selected transformer + selective LLM cascade shows no measurable change in fresh macro-F1 (0.953 → 0.954, +0.001) and accuracy (0.953 → 0.954), reviewing 22 of 1,000 fresh items. Full evaluation: $0.023671 cloud-equivalent. License: research purposes.",
  "05-ml-pipeline-churn": "On 7,043 IBM telco customers, a calibrated churn policy frozen at 0.175 from training OOF predictions costs $601 versus $1,035 for contact-everyone (95% paired bootstrap cost-delta CI -$508 to -$353). Re-select the cutoff when missed-churner cost changes.",
  "06-routing-optimization": "Routing planner for 56 Solomon 100-customer problems with time windows. Hand-written search returns feasible plans within 4.2% of best-known distance in ~1 second each, using about 3.7 more vehicles on average; an exact solver certifies small cases only.",
  "07-open-data-mobility": "Next-hour NYC taxi demand by zone, built on 41.2M real 2024 yellow-taxi trips and public weather: on a strict Oct–Dec test holdout the served GBM cuts error 28.3% vs the persistence floor (4.68 vs 6.52 MAE); its 90% band reached 90.8% coverage (no-borough zones excepted).",
  "08-inference-serving": "One laptop, five LLM serving setups, 760 requests, zero failures. The 4-bit MoE records 0.81 s p95 latency (0.63 s median) at about $0.12 per 1M output tokens (electricity only). Reuse the harness to re-measure target hardware.",
  "09-agentic-workflows": "Plan-act-review workflow with typed outcomes and deadlines. Recorded runs: 15/15 fixed tasks, 13/13 unseen answers, 5/6 correct refusals. A live re-run with hosted models: 13/13 answers, 6/6 refusals, all 19 tasks within budget.",
  "10-uplift-experimentation": "On 42,613 customers (Men's E-Mail vs No E-Mail) from the 64,000-row Hillstrom dataset, uplift targeting beat random targeting by +$2,812 (+70%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email, mailing everyone still wins. Targeting pays when sending is costly.",
  "11-data-engineering": "Ten data tasks over 2.96M NYC taxi trips, parity-checked on pandas, Polars, DuckDB and stdlib sqlite: Polars 19x, DuckDB 15x pandas; sqlite's from-files workflow is ~29x slower, with loading not timed separately; parity catches 1,658 dropped trips. NYC TLC 2024-01.",
  "12-tabular-ml-lifecycle": "Real UCI Capital Bikeshare hourly demand (17,379 rows): the validation-selected\nLightGBM reaches 23.8 test MAE vs 73.0 for the seasonal-naive floor (v2 recipe:\ntimestamp lags, `atemp` kept). The 49.2/hour gain has hourly 95% CI 44.4-54.0\nand week-block sensitivity 33.0-63.8.",
  "13-model-serving": "Project 12's v2 LightGBM (23.7636 test MAE) is rebuilt and exported to ONNX\nbehind a 2.6e-4-rental parity gate. One FastAPI schema serves both backends.\nPaired tests: 2.0 ms p50 native, ~1,012 req/s knee, 28k-41k rows/s batched;\nimage 1,060 MB, or 292 MB ONNX-only.",
  "15-dynamic-pricing-rl": "Masked PPO for constrained pricing on 600 M5-calibrated series reaches 0.5120 sealed mean profit, but trails tuned static B1 by -1.86% (paired 95% CI [-0.0114, -0.0080]); zero violations across all executable policies."
};
