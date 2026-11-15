import { parseDatasets, parseRunDetail, parseRuns } from "./contracts";
import type { Dataset, RunDetail, RunSummary, WorkbenchApi } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request(path: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Cannot reach the eval-workbench API.");
  }
  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;
    try {
      const body = (await response.json()) as { error?: { message?: string }; detail?: string };
      message = body.error?.message ?? body.detail ?? message;
    } catch {
      // Proxy errors do not necessarily use the API's JSON error envelope.
    }
    throw new ApiError(response.status, `http_${response.status}`, message);
  }
  return response.json() as Promise<unknown>;
}

export const httpApi: WorkbenchApi = {
  async datasets(signal?: AbortSignal): Promise<Dataset[]> {
    return parseDatasets(await request("/datasets", signal));
  },
  async runs(signal?: AbortSignal): Promise<RunSummary[]> {
    return parseRuns(await request("/runs", signal));
  },
  async run(id: string, signal?: AbortSignal): Promise<RunDetail> {
    return parseRunDetail(await request(`/runs/${encodeURIComponent(id)}`, signal));
  },
};
