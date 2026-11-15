import { IS_FIXTURE_MODE } from "./api";
import { ComparisonCharts } from "./components/ComparisonCharts";
import { DatasetRegistry } from "./components/DatasetRegistry";
import { RunDetail } from "./components/RunDetail";
import { RunList } from "./components/RunList";
import { Alert, EmptyState, ThemeSwitcher } from "./components/ui";
import { useWorkbench } from "./workbench/useWorkbench";

export default function App() {
  const workbench = useWorkbench();
  const connected = !workbench.loading && !workbench.error && workbench.datasets.length > 0;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workbench">Skip to evaluation workbench</a>
      <header className="app-header">
        <div className="brand">
          <span className="terminal-dots" aria-hidden="true"><span /><span /><span /></span>
          <div><h1><span>&gt;</span> eval-workbench</h1><p>versioned data · recorded runs · visible trade-offs</p></div>
        </div>
        <div className="header-controls">
          <span className={`connection-state ${connected ? "is-online" : ""}`}><i aria-hidden="true" />{workbench.loading ? "Connecting…" : connected ? "API connected" : "API unavailable"}</span>
          <ThemeSwitcher />
        </div>
      </header>

      {workbench.error ? <Alert onDismiss={workbench.clearError}>{workbench.error}</Alert> : null}
      <div className="app-body">
        <DatasetRegistry
          datasets={workbench.datasets}
          selectedId={workbench.selectedDataset?.id ?? null}
          loading={workbench.loading}
          onSelect={workbench.selectDataset}
        />
        <main className="workbench" id="workbench" tabIndex={-1}>
          <div className="dataset-titlebar">
            <div>
              <span className="eyebrow">selected dataset</span>
              <h2>{workbench.selectedDataset?.name ?? "Evaluation workbench"}</h2>
              <p>{workbench.selectedDataset ? `${workbench.selectedDataset.id} · ${workbench.selectedDataset.case_count} pinned cases` : "Select a dataset to begin."}</p>
            </div>
            <button type="button" className="button" onClick={workbench.refresh} disabled={workbench.loading}>↻ Refresh records</button>
          </div>
          {IS_FIXTURE_MODE ? <p className="fixture-banner"><strong>Fixture mode.</strong> Synthetic records demonstrate the interface; they are not live model-quality evidence.</p> : null}
          {workbench.selectedDataset ? (
            <>
              <RunList runs={workbench.datasetRuns} selectedId={workbench.selectedRunId} onSelect={workbench.selectRun} />
              <div className="workspace-grid">
                <RunDetail key={workbench.selectedRunId} run={workbench.selectedRun} loading={workbench.detailLoading} />
                <ComparisonCharts runs={workbench.datasetRuns} />
              </div>
            </>
          ) : !workbench.loading ? (
            <EmptyState title="No dataset selected">Start the API and register a dataset, then refresh the workbench.</EmptyState>
          ) : null}
        </main>
      </div>
      <footer className="app-footer">
        <span>Wrong answers and execution failures are counted separately; incomplete runs are not ranked.</span>
        <span>{IS_FIXTURE_MODE ? "local fixtures · no provider calls" : "read-only evaluation records"}</span>
      </footer>
    </div>
  );
}
