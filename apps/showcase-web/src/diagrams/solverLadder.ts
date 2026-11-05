import type { DiagramSpec } from "./types";

// Facts: projects/06-routing-optimization/{README.md,reports/metrics.json}.
export const SOLVER_LADDER_SPEC = {
  id: "06-solver-ladder",
  title: "The eight-rung solver ladder (means over 56 instances)",
  direction: "LR",
  canvasHeight: 460,
  nodes: [
    {
      id: "randomized",
      label: "randomized · feasible floor",
      kind: "source",
      facts: [
        "Mean distance gap 316.95% vs best-known; 18.3 mean vehicles (+11.09).",
        "Seeded shuffle packed into feasible routes; 0.6 ms mean runtime.",
      ],
    },
    {
      id: "nearest-neighbor",
      label: "nearest_neighbor",
      kind: "model",
      facts: [
        "Gap 71.64%, 14.0 mean vehicles; sequential insertion seeded by earliest due time.",
        "1.1 ms mean runtime.",
      ],
    },
    {
      id: "clarke-wright",
      label: "clarke_wright",
      kind: "model",
      facts: [
        "Parallel savings merges gated on capacity and time windows: gap 18.31%.",
        "13.0 mean vehicles; −68% of the randomized baseline distance.",
      ],
    },
    {
      id: "two-opt",
      label: "two_opt",
      kind: "model",
      facts: [
        "Feasible intra-route reversals plus inter-route tail exchanges: gap 13.75%.",
        "13.0 mean vehicles; 4.1 ms mean runtime.",
      ],
    },
    {
      id: "two-opt-tuned",
      label: "two_opt_tuned · HPO",
      kind: "model",
      facts: [
        "Seeded knob search: gap 13.63%, −0.45 points over untuned.",
        "Honest negative: randomized restarts never pay (k=1 chosen).",
      ],
    },
    {
      id: "alns",
      label: "alns · champion",
      kind: "model",
      facts: [
        "4.23% mean gap, 11.0 mean vehicles (+3.73), ~1.15 s per instance.",
        "Wins distance on 52 of 56 instances; destroy/repair moves customers across routes.",
      ],
    },
    {
      id: "alns-fleet",
      label: "alns_fleet · vehicles-first",
      kind: "model",
      facts: [
        "Fleet-first twin: 4.30% gap for 10.9 vehicles (+3.66).",
        "10,000-per-vehicle search penalty; wins 5/56 under the benchmark convention.",
      ],
    },
    {
      id: "cp-sat-hinted",
      label: "CP-SAT · ALNS-hinted",
      kind: "gate",
      facts: [
        "10 s/instance budget with the ALNS plan injected as hint: ties ALNS 56/56, improves 0.",
        "Status UNKNOWN on all 56 at the budget — ~10× the ALNS runtime.",
      ],
    },
    {
      id: "cp-sat-unhinted",
      label: "CP-SAT · unhinted",
      kind: "output",
      facts: [
        "Equal 10 s budget, no hint, no fallback: no feasible plan on any of the 56.",
        "From scratch the exact model produces nothing at 100-customer scale.",
      ],
    },
  ],
  edges: [
    { id: "randomized-nn", source: "randomized", target: "nearest-neighbor", kind: "task", label: "greedy insertion" },
    { id: "nn-cw", source: "nearest-neighbor", target: "clarke-wright", kind: "task", label: "savings" },
    { id: "cw-two-opt", source: "clarke-wright", target: "two-opt", kind: "task", label: "polish" },
    { id: "two-opt-tuned", source: "two-opt", target: "two-opt-tuned", kind: "task", label: "HPO" },
    { id: "tuned-alns", source: "two-opt-tuned", target: "alns", kind: "task", label: "destroy + repair" },
    { id: "tuned-alns-fleet", source: "two-opt-tuned", target: "alns-fleet", kind: "task", label: "fleet-first objective" },
    { id: "alns-hinted", source: "alns", target: "cp-sat-hinted", kind: "task", label: "hinted probe" },
    { id: "alns-unhinted", source: "alns", target: "cp-sat-unhinted", kind: "task", label: "equal budget" },
  ],
} as const satisfies DiagramSpec;
