// GENERATED — do not edit.
// Map of project id → story.yaml `short_version`, baked by
// scripts/gen_story_short.py (same loader the showcase API uses). This is the
// single plain-text source for card/README/docs/SEO/social short copy
// (portfolio_core.story.ProjectStory.short_version); lib/impact.ts reads it.
// Re-run that script after changing any story.yaml; a re-run without changes
// produces byte-identical output.

export const STORY_SHORT: Record<string, string | null> = {
  "01-rag-agent": "A question-answering assistant that answers only from a pinned 593-article Wikipedia corpus and cites every claim. Retrieval finds the right passage 83% of the time, but 18 of 65 hosted answers kept unsupported claims—answers are auditable, yet not trustworthy unattended.",
  "02-demand-forecasting": "One honest protocol, two demand regimes: on dense Walmart M5 daily sales a tuned ensemble cuts forecast error to 49% vs 60% for the seasonal-naive baseline; on sparse 89%-zero retail demand the winner is the opposite—mostly-zero routing for 945 of 1,069 lumpy series.",
  "03-anomaly-detection": "On NAB at a fixed 2% alert budget, IsolationForest catches 16 of 17 labelled incident windows but fires 1,609 alerts. Deduplication plus a one-page-per-day cap cuts that to 80 pages at modest recall cost—page the alert stream, not the detector score.",
  "04-nlp-classification": "News sorter for AG News' four topics: a language model trained on all 120k articles scores 95% macro-F1 on a fresh holdout, vs 88% for a keyword model 40x faster and free; routing doubtful items to it keeps that quality while 3 of 4 items ride at keyword cost. License unknown.",
  "05-ml-pipeline-churn": "A churn scorer on real IBM telco data (7,043 customers): serving the calibrated model at a 0.175 threshold cuts decision cost 42% (601 vs 1,035 for contacting everyone; 95% bootstrap interval -485 to -343). The cutoff must be re-derived when a missed churner's price changes.",
  "06-routing-optimization": "Routing planner for the 56 standard Solomon 100-customer problems with time windows. A hand-written search returns feasible plans within 4.2% of best-known routes in ~1 second each, using 3.7 more vehicles than best-known on average; an exact solver certifies small cases only.",
  "07-open-data-mobility": "Next-hour NYC taxi demand by zone, built on 41.2M real 2024 yellow-taxi trips and public weather: on a strict Oct-Dec holdout the model was 28% more accurate than same-hour-yesterday; its 90% upper band reached 91% coverage (sparse zones excepted).",
  "08-inference-serving": "One laptop, one run: five LLM serving setups, 760 requests, zero failures. A 4-bit mixture-of-experts model answers in 0.81 s per request at about $0.12 per 1M output tokens (electricity only). The reusable asset is the harness for re-measuring any stack on target hardware.",
  "09-agentic-workflows": "An auditable plan-act-review AI workflow with fixed tools and budgets passed all automated checks: 15/15 fixed tasks, 13/13 unseen answers, 5/6 should-fail probes, ~$0.13 per suite. Ready for supervised pilots, not unattended use. Data: synthetic handbook, real Wikipedia chunks.",
  "10-uplift-experimentation": "On 64,000-customer randomized email data, uplift targeting beat random targeting by +$2,812 (+69%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email, mailing everyone still wins. Targeting pays when sending is costly. Data: Hillstrom MineThatData, March 2008."
};
