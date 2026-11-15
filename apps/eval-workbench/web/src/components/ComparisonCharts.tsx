import type { ReactNode } from "react";
import type { RunMetrics, RunSummary } from "../api/types";
import { EmptyState } from "./ui";

type MetricKey = keyof RunMetrics;

function Chart({
  title,
  description,
  runs,
  metric,
  format,
  fixedMaximum,
}: {
  title: string;
  description: string;
  runs: RunSummary[];
  metric: MetricKey;
  format: (value: number) => string;
  fixedMaximum?: number;
}) {
  const values = runs.map((run) => run.metrics![metric]);
  const maximum = fixedMaximum ?? Math.max(...values, Number.EPSILON);
  return (
    <figure className="metric-chart">
      <figcaption><strong>{title}</strong><span>{description}</span></figcaption>
      <ol>
        {runs.map((run) => {
          const value = run.metrics![metric];
          return (
            <li key={run.id} aria-label={`${run.model}: ${format(value)}`}>
              <div className="metric-chart__label"><span>{run.model}</span><strong>{format(value)}</strong></div>
              <div className="metric-chart__track" aria-hidden="true">
                <span style={{ width: `${Math.max((value / maximum) * 100, value > 0 ? 2 : 0)}%` }} />
              </div>
            </li>
          );
        })}
      </ol>
      <div className="metric-chart__axis" aria-hidden="true"><span>0</span><span>{format(maximum)}</span></div>
    </figure>
  );
}

function ComparisonTable({ runs }: { runs: RunSummary[] }): ReactNode {
  return (
    <div className="comparison-table-wrap">
      <table className="comparison-table">
        <caption>Exact values for every completed run in this comparison</caption>
        <thead><tr><th scope="col">Model</th><th scope="col">Accuracy</th><th scope="col">F1</th><th scope="col">p95</th><th scope="col">Cost</th></tr></thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <th scope="row">{run.model}<code>{run.id}</code></th>
              <td>{run.metrics!.accuracy.toFixed(3)}</td>
              <td>{run.metrics!.f1.toFixed(3)}</td>
              <td>{run.metrics!.p95_latency_ms.toLocaleString()} ms</td>
              <td>${run.metrics!.cost_usd.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ComparisonCharts({ runs }: { runs: RunSummary[] }) {
  const completed = runs.filter((run) => run.status === "completed" && run.metrics !== null);
  return (
    <section className="panel comparison" aria-labelledby="comparison-title">
      <div className="panel__heading">
        <div><span className="eyebrow">same data · same metrics</span><h2 id="comparison-title">Model comparison</h2></div>
        <span className="count-chip">{completed.length}</span>
      </div>
      {completed.length === 0 ? <EmptyState title="Nothing to compare">Completed runs with metrics will appear here.</EmptyState> : (
        <>
          <p className="comparison__intro">Quality: higher is better. Latency and cost: lower is better. Each bar is one run, not an average across models.</p>
          <div className="chart-grid">
            <Chart title="Accuracy" description="Share of cases passed · 0–1" runs={completed} metric="accuracy" format={(value) => value.toFixed(2)} fixedMaximum={1} />
            <Chart title="F1 score" description="Balance of precision and recall · 0–1" runs={completed} metric="f1" format={(value) => value.toFixed(2)} fixedMaximum={1} />
            <Chart title="p95 latency" description="95th-percentile case latency · milliseconds" runs={completed} metric="p95_latency_ms" format={(value) => `${value.toLocaleString()} ms`} />
            <Chart title="Recorded cost" description="Total run cost · USD" runs={completed} metric="cost_usd" format={(value) => `$${value.toFixed(3)}`} />
          </div>
          <ComparisonTable runs={completed} />
        </>
      )}
    </section>
  );
}
