import type { RunSummary } from "../api/types";
import { formatDateTime, StatusBadge } from "./ui";

export function RunList({
  runs,
  selectedId,
  onSelect,
}: {
  runs: RunSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="run-browser" aria-labelledby="run-browser-title">
      <div className="section-heading">
        <div><span className="eyebrow">execution history</span><h2 id="run-browser-title">Evaluation runs</h2></div>
        <span className="muted">{runs.length} recorded</span>
      </div>
      {runs.length === 0 ? <p className="loading-copy">No runs recorded for this dataset.</p> : (
        <div className="run-list" role="list">
          {runs.map((run) => (
            <div role="listitem" key={run.id}>
              <button
                type="button"
                className={`run-card ${selectedId === run.id ? "is-selected" : ""}`}
                aria-pressed={selectedId === run.id}
                onClick={() => onSelect(run.id)}
              >
                <span className="run-card__topline"><strong>{run.model}</strong><StatusBadge status={run.status} /></span>
                <code>{run.id}</code>
                <span>{run.case_count} cases · {run.failed_cases} execution failures</span>
                <time dateTime={run.created_at}>{formatDateTime(run.created_at)}</time>
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
