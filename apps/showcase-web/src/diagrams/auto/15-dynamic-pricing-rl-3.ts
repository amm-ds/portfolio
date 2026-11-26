import type { DiagramSpec } from "../types";

// Hand-built from 15-dynamic-pricing-rl/story.yaml (training section); the
// story had no mermaid source, so scripts/mermaid-to-flow.mjs never emitted
// it. Draws only what that section states. facts stay empty, as on every
// auto spec.
export const AUTO_15_DYNAMIC_PRICING_RL_3_SPEC = {
  id: "auto-15-dynamic-pricing-rl-3",
  title: "Dynamic Pricing with RL — Training & methods",
  direction: "LR",
  nodes: [
    {
      id: "env",
      label: "PricingEnv, 91 days · 7 price steps 0.70× to 1.30×",
      kind: "tool",
      facts: [],
    },
    {
      id: "mask",
      label: "action mask · ≤1 step per change, 7-day wait",
      kind: "gate",
      facts: [],
    },
    {
      id: "encoder",
      label: "HistoryEncoder · 14 days, 2 Conv1d layers, 16 channels",
      kind: "model",
      facts: [],
    },
    {
      id: "ppo",
      label: "MaskablePPO · [64, 64] policy and value nets",
      kind: "model",
      facts: [],
    },
    {
      id: "seeds",
      label: "seeds 0 / 1 / 2 · 3,000,000 steps each",
      kind: "task",
      facts: [],
    },
    {
      id: "val",
      label: "validation, 300 episodes · seed 1 kept, 0 violations",
      kind: "gate",
      facts: [],
    },
  ],
  edges: [
    { id: "env-mask", source: "env", target: "mask", kind: "task" },
    { id: "mask-ppo", source: "mask", target: "ppo", kind: "task" },
    { id: "encoder-ppo", source: "encoder", target: "ppo", kind: "task" },
    { id: "ppo-seeds", source: "ppo", target: "seeds", kind: "task" },
    { id: "seeds-val", source: "seeds", target: "val", kind: "task" },
  ],
} as const satisfies DiagramSpec;
