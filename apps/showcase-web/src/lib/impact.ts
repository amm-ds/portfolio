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
