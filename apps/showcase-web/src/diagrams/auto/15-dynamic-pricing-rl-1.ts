import type { DiagramSpec } from "../types";

// Hand-built from 15-dynamic-pricing-rl/story.yaml (objectives section); the
// story had no mermaid source, so scripts/mermaid-to-flow.mjs never emitted
// it. Draws only what that section states. facts stay empty, as on every
// auto spec.
export const AUTO_15_DYNAMIC_PRICING_RL_1_SPEC = {
  id: "auto-15-dynamic-pricing-rl-1",
  title: "Dynamic Pricing with RL — Target & objectives",
  direction: "LR",
  nodes: [
    {
      id: "sealed",
      label: "sealed test · 1,000 episodes",
      kind: "data",
      facts: [],
    },
    {
      id: "p1",
      label: "P1 primary: RL beats locked B1 · by ≥1.0%, paired 95% CI > 0",
      kind: "gate",
      facts: [],
    },
    {
      id: "p2",
      label: "P2 hard gate: 0 violations · for B0–B3 and RL",
      kind: "gate",
      facts: [],
    },
    {
      id: "p3",
      label: "P3 context only: bound share by rho · elasticity stress −1.5 / −3.5",
      kind: "task",
      facts: [],
    },
    {
      id: "verdict",
      label: "verdict from P1 and P2 · P3 cannot rescue a failed P1",
      kind: "output",
      facts: [],
    },
  ],
  edges: [
    { id: "sealed-p1", source: "sealed", target: "p1", kind: "task" },
    { id: "sealed-p2", source: "sealed", target: "p2", kind: "task" },
    { id: "sealed-p3", source: "sealed", target: "p3", kind: "task" },
    { id: "p1-verdict", source: "p1", target: "verdict", kind: "task" },
    { id: "p2-verdict", source: "p2", target: "verdict", kind: "task" },
    { id: "p3-verdict", source: "p3", target: "verdict", kind: "result", label: "context" },
  ],
} as const satisfies DiagramSpec;
