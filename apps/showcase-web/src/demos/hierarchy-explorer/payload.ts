import { getDemoManifest, getDemoPayload } from "../../api";
import type { DemoManifest, HierarchyPayload } from "../types";

/** Fetch the demo manifest (`GET /demos/{id}/manifest`). Uses the dedicated
 * `getDemoManifest` helper — the real route has no trailing `/payload`
 * (the forecast workbench's `getDemoPayload(`${id}/manifest`)` form 404s and
 * silently falls back; here the fetched manifest is the one rendered). */
export function fetchManifest(demoId: string): Promise<DemoManifest> {
  return getDemoManifest(demoId);
}

/** Fetch the committed demo payload (`GET /demos/{id}/payload`). */
export function fetchHierarchyPayload(demoId: string): Promise<HierarchyPayload> {
  return getDemoPayload<HierarchyPayload>(demoId);
}
