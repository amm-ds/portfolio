/** One-line impact statements per project, keyed by project id. Static (not
 * served by the API — portfolio.yaml carries no impact field); wording mirrors
 * the "Impact in one line" column in docs/projects/index.md. */
export const IMPACT_LINES: Record<string, string> = {
  "01-rag-agent":
    "retrieval recall@5 0.83 vs 0.03 random; verify loop cuts unsupported claims 18→14",
  "02-demand-forecasting":
    "only model beating the seasonal floor on real intermittent demand (MASE 0.98)",
  "03-anomaly-detection":
    "catches 73% of real incidents; alert budget quantifies the false-positive cost",
  "04-nlp-classification": "full-data fine-tune reaches 0.946 macro-F1 on a laptop GPU",
  "05-ml-pipeline-churn":
    "cuts retention-campaign cost 41.9% vs the naive policy (CI excludes zero)",
  "06-routing-optimization":
    "within 4.23% of best-known solutions on all 56 instances (+3.73 vehicles)",
  "07-open-data-mobility":
    "−28.4% demand error on 41.2M trips; p90 staffing band calibrated at 90.8%",
  "08-inference-serving":
    "measured latency/throughput frontier across engines, quants, concurrency",
  "09-agentic-workflows":
    "all 15 graded tasks pass on a hosted model at ≈$0.008/task (cloud-equivalent)",
  "10-uplift-experimentation":
    "targeting profit advantage established by paired bootstrap; mail-everyone named as the bar",
};

/** Impact line for a project, or undefined if the id is not in the map. */
export function impactLine(projectId: string): string | undefined {
  return IMPACT_LINES[projectId];
}

/** 1–2 sentence "what it achieves" summaries per project, keyed by project id.
 * Static (not served by the API — portfolio.yaml carries no summary field);
 * shown on the projects index cards above the impact metric line. */
export const SUMMARIES: Record<string, string> = {
  "01-rag-agent":
    "A retrieval-augmented agent that answers questions over a Wikipedia corpus, retrieves evidence with hybrid search, and verifies each claim against its sources before answering.",
  "02-demand-forecasting":
    "Hierarchical demand forecasts for intermittent retail series that beat the seasonal-naive floor on real transaction data, with reconciliation across product levels.",
  "03-anomaly-detection":
    "Unsupervised incident detection on telemetry streams with an explicit alert budget, quantifying the recall vs false-positive cost trade-off.",
  "04-nlp-classification":
    "Fine-tuned transformer classifiers for news-topic tagging that reach strong macro-F1 on a single laptop GPU through a reproducible training pipeline.",
  "05-ml-pipeline-churn":
    "An end-to-end churn pipeline — features, training, CI-evaluated model registry — that prescribes who to target and cuts retention-campaign cost.",
  "06-routing-optimization":
    "Heuristics and exact methods for vehicle routing that come within a few percent of best-known solutions on standard benchmark instances.",
  "07-open-data-mobility":
    "A reproducible pipeline over 41M+ real taxi trips joined with weather data, producing demand forecasts with calibrated staffing bands.",
  "08-inference-serving":
    "A serving benchmark that measures the latency/throughput frontier of open models across inference engines, quantizations, and concurrency levels.",
  "09-agentic-workflows":
    "Agentic workflows (planning, tool use, graded tasks) that run a fixed task suite on hosted models at a measured per-task cost.",
  "10-uplift-experimentation":
    "Uplift modeling with paired-bootstrap evaluation that identifies who to target for retention campaigns — and when mailing everyone wins.",
};

/** Summary for a project, or undefined if the id is not in the map. */
export function summaryLine(projectId: string): string | undefined {
  return SUMMARIES[projectId];
}
