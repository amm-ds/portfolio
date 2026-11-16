// GENERATED — do not edit.
// Map of project id → story.yaml `short_version`, baked by
// scripts/gen_story_short.py (same loader the showcase API uses). This is the
// single plain-text source for card/SEO/social short copy
// (portfolio_core.story.ProjectStory.short_version); lib/impact.ts reads it.
// README/docs copies are checked by scripts/check_short_copy.py, not written here.
// Re-run that script after changing any story.yaml; a re-run without changes
// produces byte-identical output.

export const STORY_SHORT: Record<string, string | null> = {
  "01-rag-agent": "A cited QA assistant over 593 pinned Wikipedia articles. Tuning (65 q): 46 correct, 17 unsupported-claim outcomes. Sealed held-out (55 q): 44 of 55 correct; 9 of 11 failures kept unsupported claims despite rank-1 retrieval; refusal accuracy 0.92. Auditable, not unattended-ready.",
  "02-demand-forecasting": "Walmart M5 at full scale: 30,490 series scored once on the competition window under the official 42,840-node hierarchical WRMSSE. A stability-screened ensemble of pooled LightGBM fits reaches 0.6161 vs the naive floor's 0.8929 (−31.0%) — in the competition winner's ballpark.",
  "03-anomaly-detection": "On NAB at a fixed 2% alert budget, IsolationForest catches 16 of 17 incident windows but fires 1,609 alerts. A one-page-per-day cap cuts that to 80 pages; a rank-average ensemble halves the load again at higher recall — page the alert stream, not the detector score.",
  "04-nlp-classification": "AG News sorter: the selected transformer + selective LLM cascade lifts fresh macro-F1 from 0.9529432 to 0.9539265 and accuracy from 0.953 to 0.954, reviewing 22 of 1,000 fresh items. Full evaluation: $0.023671 cloud-equivalent. License unknown.",
  "05-ml-pipeline-churn": "On 7,043 IBM telco customers, a calibrated churn policy frozen at 0.175 from training OOF predictions costs 601 versus 1,035 for contact-everyone (95% paired bootstrap CI -508 to -353). Re-select the cutoff when missed-churner cost changes.",
  "06-routing-optimization": "Routing planner for the 56 standard Solomon 100-customer problems with time windows. A hand-written search returns feasible plans within 4.2% of best-known routes in ~1 second each, using 3.7 more vehicles than best-known on average; an exact solver certifies small cases only.",
  "07-open-data-mobility": "Next-hour NYC taxi demand by zone, built on 41.2M real 2024 yellow-taxi trips and public weather: on a strict Oct–Dec test holdout the served GBM cuts error 28.3% below same-hour-yesterday (4.68 vs 6.52 MAE); its 90% band reached 91% coverage (no-borough zones excepted).",
  "08-inference-serving": "One laptop, one run: five LLM serving setups, 760 requests, zero failures. A 4-bit mixture-of-experts model answers in 0.81 s per request at about $0.12 per 1M output tokens (electricity only). The reusable asset is the harness for re-measuring any stack on target hardware.",
  "09-agentic-workflows": "Auditable plan-act-review workflow with typed terminal outcomes and enforced deadlines. Legacy: 15/15 fixed answers, 13/13 unseen answers, 5/6 refusals, 18/19 steps, 12/19 latency; ~$0.13/tuning suite. Live confirmation pending.",
  "10-uplift-experimentation": "On 64,000-customer randomized email data, uplift targeting beat random targeting by +$2,812 (+69%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email, mailing everyone still wins. Targeting pays when sending is costly. Data: Hillstrom MineThatData, March 2008.",
  "11-data-engineering": "Ten data tasks over 2.96M NYC taxi trips, parity-checked on pandas, Polars, DuckDB and stdlib sqlite: Polars 19x, DuckDB 15x pandas; sqlite answers every SQL task but file conversion leaves it ~29x slower; 1M-10M tracks show the fast two scaling sub-linearly. NYC TLC 2024-01.",
  "12-tabular-ml-lifecycle": "Real UCI Capital Bikeshare hourly demand (17,379 rows): the validation-selected\nPyTorch MLP reaches 25.4 test MAE vs 83.2 for the seasonal-naive floor. The\n57.8/hour gain has hourly 95% CI 52.5-63.1 and week-block sensitivity 38.8-73.4.",
  "13-model-serving": "Experiment 12's champion MLP (25.4316 test MAE) is re-derived, exported to\nONNX behind a hard parity gate (7.2e-07 max-abs), and served two ways from\none FastAPI schema. Seeded paired tests: 1.6 ms p50, ~950 req/s knee, ~56k\nrows/s batched; image 6.5 GB, mostly unused CUDA."
};
