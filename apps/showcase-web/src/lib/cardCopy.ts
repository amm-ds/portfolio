// Experiment-card copy for the projects index. Each card body is split into
// two muted blocks: "what it does" (objective + data + approach) on the left
// and "what it achieves" (the measured result) on the right. Both are
// rewritten from the project's story.yaml `short_version` (see
// lib/storyShort.ts, the generated single source); storyShort.ts itself stays
// untouched — it still feeds ProjectDetail SEO descriptions and README/docs
// copy; the index cards need the tighter two-block shape.

/** "What it does" per project id — objective, data and approach. Key facts
 *  carry `**bold**` inline markdown so they stand out in the muted card body
 *  (rendered by StudyCard through renderInlineMarkdown). */
export const CARD_DOES: Record<string, string> = {
  "01-rag-agent":
    "Built a question-answering agent that answers only from a pinned **593-article** Wikipedia corpus and cites every claim.",
  "02-demand-forecasting":
    "Forecasts all **30,490** Walmart M5 store-item series through a **42,840-node hierarchy** and grades every candidate under the competition's official weighted error.",
  "03-anomaly-detection":
    "Screens NAB telemetry at a fixed **2% alert budget** with an isolation-forest scorer that flags anomalous windows.",
  "04-nlp-classification":
    "Sorts AG News into its four topics, training a language model on all **120k articles** against a **40x-faster** keyword model.",
  "05-ml-pipeline-churn":
    "Scores churn on IBM telco data (**7,043 customers**) and serves the calibrated model at a **0.175 threshold**.",
  "06-routing-optimization":
    "Plans routes for the **56 standard Solomon 100-customer problems** with time windows using a hand-written search.",
  "07-open-data-mobility":
    "Forecasts next-hour NYC taxi demand by zone from **41.2M real 2024 yellow-taxi trips** plus public weather.",
  "08-inference-serving":
    "Benchmarks **five LLM serving setups** on one laptop with **760 requests** and zero failures.",
  "09-agentic-workflows":
    "Runs an auditable plan-act-review agent workflow over a synthetic **12-document handbook** plus a read-only Wikipedia slice.",
  "10-uplift-experimentation":
    "Evaluates uplift targeting on **64,000-customer** randomized email data (Hillstrom MineThatData, March 2008) at a **25% send budget**.",
};

/** "What it achieves" per project id — the measured result. Key numbers are
 *  **bold** so the result scans at a glance. */
export const CARD_ACHIEVES: Record<string, string> = {
  "01-rag-agent":
    "Retrieval finds the right passage **83% of the time**, but **18 of 65** audited answers kept unsupported claims — auditable, not yet trustworthy unattended.",
  "02-demand-forecasting":
    "A stability-screened ensemble of pooled LightGBM fits reaches **0.6161** vs the naive floor's **0.8929** official WRMSSE (**−31.0%**) on the scored-once competition window.",
  "03-anomaly-detection":
    "IsolationForest catches **16 of 17** labelled incident windows but fires 1,609 raw alerts; deduplication plus a one-page-per-day cap cuts the stream to **80 pages** at modest recall cost.",
  "04-nlp-classification":
    "The language model scores **95% macro-F1** on a fresh holdout vs **88%** for the keyword model; routing doubtful items to it keeps that quality while **3 of 4 items** ride at keyword cost.",
  "05-ml-pipeline-churn":
    "Cutting decision cost **42%** vs contacting everyone (**601 vs 1,035**; 95% bootstrap CI −485 to −343); the cutoff must be re-derived when a missed churner's price changes.",
  "06-routing-optimization":
    "Returns feasible plans within **4.2% of best-known distance** in about a second each, using 3.7 more vehicles than best-known on average; an exact solver certifies small cases only.",
  "07-open-data-mobility":
    "On a strict Oct–Dec holdout the model beats same-hour-yesterday by **28%**; its 90% upper band reaches **91% coverage** (sparse zones excepted).",
  "08-inference-serving":
    "A 4-bit mixture-of-experts model answers in **0.81 s per request** at about **$0.12 per 1M output tokens** (electricity only); the reusable asset is the harness for re-measuring any stack on target hardware.",
  "09-agentic-workflows":
    "Fixed tools and budgets pass **15/15 fixed tasks, 13/13 unseen answers and 5/6 should-fail probes** at about **$0.13 per suite** — ready for supervised pilots, not unattended use.",
  "10-uplift-experimentation":
    "Beats random targeting by **+$2,812 (+69%; CI +$718 to +$4,767)**, though at $0.01 per email mailing everyone still wins.",
  "11-data-engineering":
    "Polars runs **x17.3** and DuckDB **x14.7** over pandas on the geomean of 8 parity-checked tasks — from a **3-5x** tie on parquet IO to **110x-plus** on group-by and window work.",
};

/** Exactly four short tags per card — technique/capability wording with no
 *  framework or library names (the stack lives in the services frameworks
 *  grid). Unknown ids fall back to the first four techniques the registry
 *  serves. */
const CARD_TAGS: Record<string, string[]> = {
  "01-rag-agent": ["RAG", "vector search", "reranking", "RAG evals"],
  "02-demand-forecasting": ["GBM", "MinT", "hyperparameter search", "deep learning"],
  "03-anomaly-detection": ["IsolationForest", "LOF", "alert budgeting", "deduplication"],
  "04-nlp-classification": ["TF-IDF", "language model", "deep learning", "calibration"],
  "05-ml-pipeline-churn": ["calibration", "bootstrap CIs", "threshold tuning", "tested pipelines"],
  "06-routing-optimization": ["2-opt", "VRPTW", "ALNS", "solver tuning"],
  "07-open-data-mobility": ["data versioning", "streaming ETL", "DQ gates", "API serving"],
  "08-inference-serving": ["local inference", "quantization", "cost/token", "latency/throughput"],
  "09-agentic-workflows": ["HITL", "toolsets", "structured agents", "agent evals"],
  "10-uplift-experimentation": ["CUPED", "Qini", "power analysis", "uplift (T/X)"],
  "11-data-engineering": ["engine benchmarks", "parquet/CSV IO", "group-by & window", "memory probes"],
};

/** "What it does" block for an experiment card. */
export function cardDoes(projectId: string): string | undefined {
  return CARD_DOES[projectId];
}

/** "What it achieves" block for an experiment card. */
export function cardAchieves(projectId: string): string | undefined {
  return CARD_ACHIEVES[projectId];
}

/** Exactly four short technique tags for an experiment card. */
export function cardTags(projectId: string, techniques: string[]): string[] {
  return CARD_TAGS[projectId] ?? techniques.slice(0, 4);
}
