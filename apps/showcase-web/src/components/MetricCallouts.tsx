import type { Metrics } from "../api";
import { computeCallouts, formatMetricValue } from "../lib/delta";

/** Metric callout chips for a story section (baseline-delta aware). */
export function MetricCallouts({ metrics, metricsKeys }: { metrics: Metrics; metricsKeys: string[] }) {
  if (metricsKeys.length === 0) return null;
  const callouts = computeCallouts(metrics, metricsKeys);
  if (callouts.length === 0) return null;
  return (
    <div className="callouts">
      {callouts.map((c) => (
        <span key={c.run} className="callout-chip">
          <span className="run">[{c.run}]</span>
          <span>
            {c.metric}: <span className="value">{formatMetricValue(c.value)}</span>
          </span>
          {c.deltaPct !== null && c.baselineRun && (
            <span className={`delta ${c.improved ? "improved" : "regressed"}`}>
              {c.metric.toUpperCase()} {c.deltaPct > 0 ? "+" : ""}
              {c.deltaPct.toFixed(0)}% vs {c.baselineRun}
            </span>
          )}
        </span>
      ))}
    </div>
  );
}
