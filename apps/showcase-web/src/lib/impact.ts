/** One-line impact statements per project, keyed by project id. Static (not
 * served by the API — portfolio.yaml carries no impact field); wording mirrors
 * the "Impact in one line" column in docs/projects/index.md. */
export const IMPACT_LINES: Record<string, string> = {
  "01-rag-agent":
    "retrieval recall@5 0.83 vs 0.03 random; verify loop cut unsupported-claim share 60%→47% in an on/off A/B (committed hosted 65-q run: 18/65)",
  "02-demand-forecasting":
    "champion runs at 0.843 relative MAE of the seasonal-naive floor on real intermittent demand (MASE 1.078 vs the naive's own 1.310)",
  "03-anomaly-detection":
    "16 of 17 labelled windows touched at 1,609 alerts — episode dedup + a 24 h page cap cuts pages to 80 and raises range-F1 0.157 → 0.315; train-side operating-point tuning halves IsolationForest pages again (80 → 46, range-F1 0.315 → 0.382) while OCSVM's marginal adoption fails to transfer — the measured limit of 6-window validation",
  "04-nlp-classification":
    "full-data fine-tune reaches 0.946 macro-F1 on a laptop GPU; a controlled same-device ladder isolates the data effect (+1.3–1.6 pp per 3× rows) from device noise (≤0.011 macro-F1)",
  "05-ml-pipeline-churn":
    "cuts retention-campaign cost 41.9% vs the naive policy (CI excludes zero)",
  "06-routing-optimization":
    "within 4.23% of best-known solutions on all 56 instances (+3.73 vehicles)",
  "07-open-data-mobility":
    "−28.3% demand error on 41.2M trips; p90 staffing band calibrated at 90.8%; the first unseen drift month (2025-01) scores in-window at −5.0%, and green-taxi demand serves from a per-service retrained bundle routed by an optional API `service` field",
  "08-inference-serving":
    "measured latency/throughput frontier across engines, quants, concurrency",
  "09-agentic-workflows":
    "15/15 on every grader on a hosted model + held-out 13/13 answers, 5/6 should-fail refusals (n=19 suite) — suite $0.13 of the $2.00 cap, cloud-equivalent; the local-provider wave meters $0.00 but breaks the hosted-tuned 60 s budget on 7/9 tasks",
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
    "Fine-tuned transformer classifiers for news-topic tagging that reach 0.946 macro-F1 on a single laptop GPU, with a controlled data-scale ladder separating device noise from the measured data-scaling slope.",
  "05-ml-pipeline-churn":
    "An end-to-end churn pipeline — features, training, CI-evaluated model registry — that prescribes who to target and cuts retention-campaign cost.",
  "06-routing-optimization":
    "Heuristics and exact methods for vehicle routing that come within a few percent of best-known solutions on standard benchmark instances.",
  "07-open-data-mobility":
    "A reproducible pipeline over 41.2M real taxi trips joined with weather data, producing demand forecasts with calibrated staffing bands, a scored drift observatory, and per-service (yellow/green) serving bundles.",
  "08-inference-serving":
    "A serving benchmark that measures the latency/throughput frontier of open models across inference engines, quantizations, and concurrency levels.",
  "09-agentic-workflows":
    "Agentic workflows (planning, tool use, graded tasks) that run a deterministic 15-task suite — a synthetic handbook corpus plus real Wikipedia retrieval via 01's index — on a hosted model at a measured, budget-capped per-suite cost.",
  "10-uplift-experimentation":
    "Uplift modeling with paired-bootstrap evaluation that identifies who to target for retention campaigns — and when mailing everyone wins.",
};

/** Summary for a project, or undefined if the id is not in the map. */
export function summaryLine(projectId: string): string | undefined {
  return SUMMARIES[projectId];
}
