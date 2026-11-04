import { getDemoPayload } from "../../api";
import type { ChurnPayload } from "../types";

/** Fetch the committed demo payload (`GET /demos/{id}/payload`). */
export function fetchChurnPayload(demoId: string): Promise<ChurnPayload> {
  return getDemoPayload<ChurnPayload>(demoId);
}
