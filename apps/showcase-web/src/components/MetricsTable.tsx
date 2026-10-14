import type { Metrics } from "../api";
import { formatMetricValue } from "../lib/delta";
import { DataTable } from "./DataTable";

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Render the nested metrics object: one row per run, one column per metric.
 *  Runs are the top-level keys; runs prefixed with "_" (e.g. "_meta") are
 *  shown as a footnote, not table rows. Non-numeric cells render as "—". */
export function MetricsTable({ metrics }: { metrics: Metrics }) {
  const runs = Object.keys(metrics).filter((run) => !run.startsWith("_"));
  const meta = metrics["_meta"];
  if (runs.length === 0) return null;
  const metricNames = [
    ...new Set(
      runs.flatMap((run) =>
        Object.entries(metrics[run])
          .filter(([, value]) => isNumber(value))
          .map(([name]) => name),
      ),
    ),
  ];
  const metaEntries = meta
    ? Object.entries(meta).filter(([, value]) => isNumber(value) || typeof value === "string")
    : [];
  return (
    <>
      <DataTable className="metrics-table">
        <thead>
          <tr>
            <th scope="col">run</th>
            {metricNames.map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run}>
              <td>{run}</td>
              {metricNames.map((name) => {
                const value = metrics[run][name];
                return <td key={name}>{isNumber(value) ? formatMetricValue(value) : "—"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </DataTable>
      {metaEntries.length > 0 && (
        <p className="muted">
          {metaEntries.map(([key, value]) =>
            `${key}: ${isNumber(value) ? formatMetricValue(value) : String(value)}`,
          ).join(" · ")}
        </p>
      )}
    </>
  );
}
