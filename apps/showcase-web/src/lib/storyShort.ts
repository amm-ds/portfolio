// GENERATED — do not edit.
// Map of project id → story.yaml `short_version`, baked by
// scripts/gen_story_short.py (same loader the showcase API uses). This is the
// single plain-text source for card/SEO/social short copy
// (portfolio_core.story.ProjectStory.short_version); lib/impact.ts reads it.
// README/docs copies are checked by scripts/check_short_copy.py, not written here.
// Re-run that script after changing any story.yaml; a re-run without changes
// produces byte-identical output.

export const STORY_SHORT: Record<string, string | null> = {
  "01-rag-agent": "Grounding-hardened cited QA over 593 Wikipedia articles. Frozen 30-question stress re-run: 0.733 correct (CI [0.567, 0.867]); unsupported outcomes 5 of 30 (was 11; not a demonstrated gain). Independent set B: 0.633, 9/30 unsupported over the ≤6/30 gate. Not unattended-ready.",
  "02-demand-forecasting": "M5 full panel: 30,490 series, one scored test origin (final 28 days) with official 42,840-node WRMSSE. Pooled LightGBM ensemble: 0.6161 vs seasonal-naive 0.8929 (−31.0%); no bootstrap interval bounds the result; quiet days favor the floor.",
  "03-anomaly-detection": "NAB, 9 evaluable series: IsolationForest touches 16/17 incidents but fires 1,609 raw alerts. Daily budgeting cuts that to 80 pages; like-for-like, the rolling-feature ensemble halves 66 budgeted pages to 35 at equal recall 0.604, range-F1 0.533. NAB official score not reported.",
  "04-nlp-classification": "AG News sorter: the selected transformer + selective LLM cascade shows no measurable change in fresh macro-F1 (0.953 → 0.954, +0.001) and accuracy (0.953 → 0.954), reviewing 22 of 1,000 fresh items. Full evaluation: $0.023671 cloud-equivalent. License: research purposes.",
  "05-ml-pipeline-churn": "On 7,043 IBM telco customers, a calibrated churn policy frozen at 0.175 from training OOF predictions costs 601 versus 1,035 for contact-everyone (95% paired bootstrap CI -508 to -353). Re-select the cutoff when missed-churner cost changes.",
  "06-routing-optimization": "Routing planner for the 56 standard Solomon 100-customer problems with time windows. A hand-written search returns feasible plans within 4.2% of best-known routes in ~1 second each, using 3.7 more vehicles than best-known on average; an exact solver certifies small cases only.",
  "07-open-data-mobility": "Next-hour NYC taxi demand by zone, built on 41.2M real 2024 yellow-taxi trips and public weather: on a strict Oct–Dec test holdout the served GBM cuts error 28.3% vs the persistence floor (4.68 vs 6.52 MAE); its 90% band reached 91% coverage (no-borough zones excepted).",
  "08-inference-serving": "One laptop, five LLM serving setups, 760 requests, zero failures. The 4-bit MoE records 0.81 s p95 latency (0.63 s median) at about $0.12 per 1M output tokens (electricity only). Reuse the harness to re-measure target hardware.",
  "09-agentic-workflows": "Auditable plan-act-review workflow with typed terminal outcomes and enforced deadlines. Legacy (run once per task): 15/15 fixed, 13/13 unseen answers, 5/6 refusals, 18/19 steps, 12/19 latency; ~$0.13/tuning suite. Live 2026-11-19: 13/13 answers, 6/6 refusals, 19/19 budgets.",
  "10-uplift-experimentation": "On 42,613 customers (Men's E-Mail vs No E-Mail) from the 64,000-row Hillstrom dataset, uplift targeting beat random targeting by +$2,812 (+70%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email, mailing everyone still wins. Targeting pays when sending is costly.",
  "11-data-engineering": "Ten data tasks over 2.96M NYC taxi trips, parity-checked on pandas, Polars, DuckDB and stdlib sqlite: Polars 19x, DuckDB 15x pandas; sqlite answers every SQL task but file conversion leaves it ~29x slower; 1M-10M tracks show the fast two scaling sub-linearly. NYC TLC 2024-01.",
  "12-tabular-ml-lifecycle": "Real UCI Capital Bikeshare hourly demand (17,379 rows): the validation-selected\nPyTorch MLP reaches 25.4 test MAE vs 83.2 for the seasonal-naive floor. The\n57.8/hour gain has hourly 95% CI 52.5-63.1 and week-block sensitivity 38.8-73.4.",
  "13-model-serving": "Experiment 12's champion MLP (25.4316 test MAE) is re-derived, exported to\nONNX behind a hard parity gate (7.2e-07 max-abs), and served two ways from\none FastAPI schema. Seeded paired tests: 1.6 ms p50, ~950 req/s knee, ~56k\nrows/s batched; image 6.5 GB, mostly unused CUDA."
};
