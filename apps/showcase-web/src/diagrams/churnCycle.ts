import type { DiagramSpec } from "./types";

// Facts: projects/05-ml-pipeline-churn/{README.md,reports/metrics.json}.
export const CHURN_CYCLE_SPEC = {
  id: "05-churn-cycle",
  title: "One retention cycle: score, cut at 0.175, price the list",
  direction: "LR",
  canvasHeight: 380,
  nodes: [
    {
      id: "crm",
      label: "Raw CRM row",
      kind: "source",
      facts: [
        "IBM telco churn: 7,043 customers behind DQ gates and a DatasetContract.",
        "26.5% holdout churn rate; a missed churner prices 5× a false alarm (FP=1, FN=5).",
      ],
    },
    {
      id: "pipeline",
      label: "One fitted pipeline",
      kind: "tool",
      facts: [
        "Caps, flags, imputes and encodes live inside one sklearn Pipeline — no preprocessing outside it.",
        "OutlierCapper clips at train-time quantiles; missingness becomes a feature before imputation.",
      ],
    },
    {
      id: "score",
      label: "Churn probability · isotonic XGBoost",
      kind: "model",
      facts: [
        "Cost-aware Optuna HPO (25 trials × 4 arms) selected XGBoost on the real track.",
        "Served model: ROC-AUC 0.8317, ECE 0.016 after isotonic calibration.",
      ],
    },
    {
      id: "cut",
      label: "Threshold 0.175",
      kind: "gate",
      facts: [
        "Cost-optimal operating point under FP=1, FN=5.",
        "Re-derived per regime — the synthetic track's t*=0.700 does not transfer.",
      ],
    },
    {
      id: "list",
      label: "Contact list",
      kind: "output",
      facts: [
        "Above-threshold customers go to the retention team; the rest are not contacted.",
        "The deliverable is the priced list, not the score.",
      ],
    },
    {
      id: "holdout",
      label: "1,409-row holdout",
      kind: "data",
      facts: [
        "Stratified 80/20 split, seed 42; the holdout is scored once.",
        "Calibration is carved from training only, disjoint from the fit data.",
      ],
    },
    {
      id: "bill",
      label: "Priced outcome",
      kind: "output",
      facts: [
        "601 cost units vs 1,035 for contacting everyone: −41.9%.",
        "Paired bootstrap 95% CI −485 to −343 over 2,000 resamples.",
      ],
    },
  ],
  edges: [
    { id: "crm-pipeline", source: "crm", target: "pipeline", kind: "task", label: "raw row" },
    { id: "pipeline-score", source: "pipeline", target: "score", kind: "result", label: "transformed row" },
    { id: "score-cut", source: "score", target: "cut", kind: "result", label: "probability" },
    { id: "cut-list", source: "cut", target: "list", kind: "result", label: "above 0.175" },
    { id: "list-bill", source: "list", target: "bill", kind: "task", label: "price at FP=1, FN=5" },
    { id: "holdout-bill", source: "holdout", target: "bill", kind: "task", label: "score once" },
  ],
} as const satisfies DiagramSpec;
