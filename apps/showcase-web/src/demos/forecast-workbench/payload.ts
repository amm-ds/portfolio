import { getDemoManifest, getDemoPayload } from "../../api";
import type { DemoManifest, ForecastPayload } from "../types";

/** Fetch the demo manifest (`GET /demos/{id}/manifest`). */
export function fetchManifest(demoId: string): Promise<DemoManifest> {
  return getDemoManifest(demoId);
}

/** Fetch the committed demo payload (`GET /demos/{id}/payload`). */
export function fetchForecastPayload(demoId: string): Promise<ForecastPayload> {
  return getDemoPayload<ForecastPayload>(demoId);
}
