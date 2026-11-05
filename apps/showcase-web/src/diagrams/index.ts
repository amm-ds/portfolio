import { AGENT_LOOP_SPEC } from "./agentLoop";
import { ROUTING_SPEC } from "./routing";
import type { DiagramSpec } from "./types";

export const DIAGRAM_SPECS = {
  "09-agent-loop": AGENT_LOOP_SPEC,
  "04-routing": ROUTING_SPEC,
} as const satisfies Record<string, DiagramSpec>;

export type DiagramSpecId = keyof typeof DIAGRAM_SPECS;

export function getDiagramSpec(specId: string): DiagramSpec | undefined {
  if (!Object.prototype.hasOwnProperty.call(DIAGRAM_SPECS, specId)) return undefined;
  return DIAGRAM_SPECS[specId as DiagramSpecId];
}

export { AGENT_LOOP_SPEC, ROUTING_SPEC };
export type { DiagramSpec } from "./types";
