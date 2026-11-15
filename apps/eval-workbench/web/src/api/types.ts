/** JSON contracts mirrored from the eval-workbench FastAPI models. */
export type RunStatus = "queued" | "running" | "completed" | "failed";
export const RUN_STATUSES = ["queued", "running", "completed", "failed"] as const;

export interface Dataset {
  id: string;
  name: string;
  version: string;
  description: string;
  case_count: number;
  tags: string[];
  created_at: string;
}

export interface RunMetrics {
  accuracy: number;
  f1: number;
  p95_latency_ms: number;
  cost_usd: number;
}

export interface RunSummary {
  id: string;
  dataset_id: string;
  model: string;
  status: RunStatus;
  case_count: number;
  failed_cases: number;
  metrics: RunMetrics | null;
  created_at: string;
  completed_at: string | null;
}

export interface RunCase {
  id: string;
  input: string;
  expected: string;
  output: string | null;
  passed: boolean;
  latency_ms: number;
  error: string | null;
}

export interface RunDetail extends RunSummary {
  cases: RunCase[];
}

export interface WorkbenchApi {
  datasets(signal?: AbortSignal): Promise<Dataset[]>;
  runs(signal?: AbortSignal): Promise<RunSummary[]>;
  run(id: string, signal?: AbortSignal): Promise<RunDetail>;
}
