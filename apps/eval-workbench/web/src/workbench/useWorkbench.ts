import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Dataset, RunDetail, RunSummary } from "../api/types";

export function useWorkbench() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([api.datasets(controller.signal), api.runs(controller.signal)])
      .then(([nextDatasets, nextRuns]) => {
        setDatasets(nextDatasets);
        setRuns(nextRuns);
        setSelectedDatasetId((current) =>
          current && nextDatasets.some((item) => item.id === current) ? current : (nextDatasets[0]?.id ?? null),
        );
        setSelectedRunId((current) => (current && nextRuns.some((item) => item.id === current) ? current : null));
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "The workbench could not load its records.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    setSelectedRunId((current) => {
      if (current && runs.some((run) => run.id === current && run.dataset_id === selectedDatasetId)) return current;
      return runs.find((run) => run.dataset_id === selectedDatasetId)?.id ?? null;
    });
  }, [runs, selectedDatasetId]);

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    setSelectedRun(null);
    api.run(selectedRunId, controller.signal)
      .then(setSelectedRun)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError(reason instanceof Error ? reason.message : "The run detail could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedRunId]);

  const datasetRuns = useMemo(
    () => runs.filter((run) => run.dataset_id === selectedDatasetId),
    [runs, selectedDatasetId],
  );
  const selectedDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) ?? null;

  function selectDataset(id: string) {
    setSelectedDatasetId(id);
    setSelectedRunId(runs.find((run) => run.dataset_id === id)?.id ?? null);
    setError(null);
  }

  return {
    datasets,
    runs,
    datasetRuns,
    selectedDataset,
    selectedRunId,
    selectedRun,
    loading,
    detailLoading,
    error,
    refresh,
    selectDataset,
    selectRun: setSelectedRunId,
    clearError: () => setError(null),
  };
}

export type Workbench = ReturnType<typeof useWorkbench>;
