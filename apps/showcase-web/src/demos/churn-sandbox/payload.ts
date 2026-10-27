import { getDemoManifest, getDemoPayload } from "../../api";
import type { ChurnPayload, DemoManifest } from "../types";

/** Fetch the demo manifest (`GET /demos/{id}/manifest`). */
export function fetchManifest(demoId: string): Promise<DemoManifest> {
  return getDemoManifest(demoId);
}

/** Fetch the committed demo payload (`GET /demos/{id}/payload`). */
export function fetchChurnPayload(demoId: string): Promise<ChurnPayload> {
  return getDemoPayload<ChurnPayload>(demoId);
}
