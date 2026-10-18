import type { Metrics } from "../api";
import { computeCallouts, formatMetricValue } from "../lib/delta";
import { DataTable } from "./DataTable";

/**
 * Compact results table for a story section's referenced runs (replaces the
 * old metric callout chips). One row per run in `metricsKeys`, showing the
 * run's headline metric and value; when a baseline is present the best run
 * gets a signed delta column entry (baseline-delta aware, same logic the
 * chips used). Renders nothing without metrics_keys or matching runs.
 */
export function StoryMetricsTable({ metrics, metricsKeys }: { metrics: Metrics; metricsKeys: string[] }) {
  if (metricsKeys.length === 0) return null;
  const callouts = computeCallouts(metrics, metricsKeys);
  if (callouts.length === 0) return null;
  const hasDelta = callouts.some((c) => c.deltaPct !== null);
  return (
    <DataTable className="story-metrics-table">
      <thead>
        <tr>
          <th scope="col">run</th>
          <th scope="col">metric</th>
          <th scope="col">value</th>
          {hasDelta && <th scope="col">Δ vs baseline</th>}
        </tr>
      </thead>
      <tbody>
        {callouts.map((c) => (
          <tr key={c.run}>
            <td>{c.run}</td>
            <td>{c.metric}</td>
            <td className="value">{formatMetricValue(c.value)}</td>
            {hasDelta && (
              <td>
                {c.deltaPct !== null && c.baselineRun ? (
                  <span className={`delta ${c.improved ? "improved" : "regressed"}`}>
                    {c.deltaPct > 0 ? "+" : ""}
                    {c.deltaPct.toFixed(0)}% vs {c.baselineRun}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
