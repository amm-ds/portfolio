import type { Metrics } from "../api";
import { formatMetricValue } from "../lib/delta";
import { DataTable } from "./DataTable";

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Render the nested metrics object: one row per run, one column per metric.
 *  Runs are the top-level keys whose value is a record; runs prefixed with
 *  "_" (e.g. "_meta") are shown as a footnote, not table rows. Top-level
 *  non-record values (lists, strings — e.g. 02's `candidates`) are metadata
 *  and are skipped. Non-numeric cells render as "—". */
export function MetricsTable({ metrics }: { metrics: Metrics }) {
  const runEntries = Object.entries(metrics).filter(
    (entry): entry is [string, Record<string, unknown>] =>
      !entry[0].startsWith("_") && isRecord(entry[1]),
  );
  const meta = metrics["_meta"];
  if (runEntries.length === 0) return null;
  const metricNames = [
    ...new Set(
      runEntries.flatMap(([, run]) =>
        Object.entries(run)
          .filter(([, value]) => isNumber(value))
          .map(([name]) => name),
      ),
    ),
  ];
  const metaEntries = isRecord(meta)
    ? Object.entries(meta).filter(([, value]) => isNumber(value) || typeof value === "string")
    : [];
  return (
    <>
      <DataTable className="metrics-table" ariaLabel="Run metrics">
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
          {runEntries.map(([run, values]) => (
            <tr key={run}>
              <td>{run}</td>
              {metricNames.map((name) => {
                const value = values[name];
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
