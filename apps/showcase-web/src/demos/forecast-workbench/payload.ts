import { getDemoManifest, getDemoPayload } from "../../api";
import type { DemoManifest, ForecastWorkbenchPayload } from "../types";

/** Fetch the demo manifest (`GET /demos/{id}/manifest`). */
export function fetchManifest(demoId: string): Promise<DemoManifest> {
  return getDemoManifest(demoId);
}

/** Fetch the committed forecast-workbench payload (`GET /demos/{id}/payload`). */
export function fetchForecastPayload(demoId: string): Promise<ForecastWorkbenchPayload> {
  return getDemoPayload<ForecastWorkbenchPayload>(demoId);
}
