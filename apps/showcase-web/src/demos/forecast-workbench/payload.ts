import { getDemoPayload } from "../../api";
import type { ForecastWorkbenchPayload } from "../types";

/** Fetch the committed forecast-workbench payload (`GET /demos/{id}/payload`). */
export function fetchForecastPayload(demoId: string): Promise<ForecastWorkbenchPayload> {
  return getDemoPayload<ForecastWorkbenchPayload>(demoId);
}
