import { useEffect, useState } from "react";
import type { RunDetail as RunDetailRecord } from "../api/types";
import { EmptyState, formatDateTime, StatusBadge } from "./ui";

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function RunDetail({ run, loading }: { run: RunDetailRecord | null; loading: boolean }) {
  const [failuresOnly, setFailuresOnly] = useState(false);
  useEffect(() => setFailuresOnly(false), [run?.id]);

  if (loading) return <section className="panel run-detail"><p className="loading-copy" role="status">Loading run detail…</p></section>;
  if (!run) return <section className="panel run-detail"><EmptyState title="No run selected">Select an evaluation run to inspect its cases and measurements.</EmptyState></section>;

  const failedPredictions = run.cases.filter((item) => !item.passed).length;
  const visibleCases = failuresOnly ? run.cases.filter((item) => !item.passed || item.error) : run.cases;

  return (
    <section className="panel run-detail" aria-labelledby="run-detail-title">
      <div className="panel__heading">
        <div><span className="eyebrow">run record</span><h2 id="run-detail-title">{run.model}</h2></div>
        <StatusBadge status={run.status} />
      </div>
      <div className="run-identity">
        <code>{run.id}</code>
        <span>{formatDateTime(run.created_at)}</span>
      </div>
      {run.metrics ? (
        <dl className="metric-grid">
          <div><dt>Accuracy</dt><dd>{percent(run.metrics.accuracy)}</dd></div>
          <div><dt>F1</dt><dd>{run.metrics.f1.toFixed(3)}</dd></div>
          <div><dt>p95 latency</dt><dd>{run.metrics.p95_latency_ms.toLocaleString()} ms</dd></div>
          <div><dt>Run cost</dt><dd>${run.metrics.cost_usd.toFixed(3)}</dd></div>
        </dl>
      ) : (
        <p className="notice">Metrics are unavailable until a run completes successfully.</p>
      )}
      <div className="case-heading">
        <div><h3>Case results</h3><p>{run.cases.length} inspected · {failedPredictions} incorrect · {run.failed_cases} execution failures</p></div>
        <div className="segmented" role="group" aria-label="Case result filter">
          <button type="button" aria-pressed={!failuresOnly} onClick={() => setFailuresOnly(false)}>All</button>
          <button type="button" aria-pressed={failuresOnly} onClick={() => setFailuresOnly(true)}>Needs review</button>
        </div>
      </div>
      <div className="case-table-wrap">
        {visibleCases.length === 0 ? <p className="loading-copy">No cases match this filter.</p> : (
          <table className="case-table">
            <caption className="sr-only">Expected and actual outputs for {run.model}</caption>
            <thead><tr><th scope="col">Result</th><th scope="col">Input</th><th scope="col">Expected</th><th scope="col">Output</th><th scope="col">Latency</th></tr></thead>
            <tbody>
              {visibleCases.map((item) => (
                <tr key={item.id}>
                  <td><span className={`case-result ${item.passed && !item.error ? "is-pass" : "is-fail"}`}>{item.error ? "error" : item.passed ? "pass" : "miss"}</span></td>
                  <td><span className="case-input" title={item.input}>{item.input}</span><code>{item.id}</code></td>
                  <td><code>{item.expected}</code></td>
                  <td>{item.error ? <span className="error-copy">{item.error}</span> : <code>{item.output ?? "—"}</code>}</td>
                  <td>{item.latency_ms.toLocaleString()} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
