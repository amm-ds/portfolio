import type { DiagramSpec } from "../types";

// Hand-built from 15-dynamic-pricing-rl/story.yaml (conclusions section); the
// story had no mermaid source, so scripts/mermaid-to-flow.mjs never emitted
// it. Draws only what that section states. facts stay empty, as on every
// auto spec.
export const AUTO_15_DYNAMIC_PRICING_RL_4_SPEC = {
  id: "auto-15-dynamic-pricing-rl-4",
  title: "Dynamic Pricing with RL — Conclusions & lessons",
  direction: "LR",
  nodes: [
    {
      id: "result",
      label: "sealed result: RL trails B1 · paired interval below zero",
      kind: "output",
      facts: [],
    },
    {
      id: "assets",
      label: "reusable assets · environment, CRN pairing, masks, fluid ceiling, tournament, audit log",
      kind: "data",
      facts: [],
    },
    {
      id: "dev",
      label: "future work on development splits · richer demand or new objectives",
      kind: "task",
      facts: [],
    },
    {
      id: "fresh",
      label: "fresh sealed protocol · consumed test set is not reused",
      kind: "gate",
      facts: [],
    },
  ],
  edges: [
    { id: "result-assets", source: "result", target: "assets", kind: "result" },
    { id: "assets-dev", source: "assets", target: "dev", kind: "task" },
    { id: "dev-fresh", source: "dev", target: "fresh", kind: "task" },
  ],
} as const satisfies DiagramSpec;
