import type { DiagramSpec } from "./types";

// Facts: projects/07-open-data-mobility/{README.md,reports/metrics.json}.
export const MOBILITY_PIPELINE_SPEC = {
  id: "07-mobility-pipeline",
  title: "Two public feeds to a served zone-hour forecast",
  direction: "LR",
  canvasHeight: 400,
  nodes: [
    {
      id: "tlc",
      label: "TLC yellow taxis 2024",
      kind: "source",
      facts: [
        "41.2M real trips across 12 monthly Parquet files, checksum-pinned.",
        "Per-month DQ contracts halt the pipeline loudly on bad data.",
      ],
    },
    {
      id: "noaa",
      label: "NOAA Central Park weather",
      kind: "source",
      facts: [
        "GHCN-Daily weather for the same city and period.",
        "Weather features ≈ 0 for point MAE — their value is the elasticity read.",
      ],
    },
    {
      id: "join",
      label: "Join + data-quality gates",
      kind: "tool",
      facts: [
        "Streaming Polars aggregation — the pipeline never materialises raw trips.",
        "Observed pipeline peak ≈ 1.8 GB RAM on 41M rows.",
      ],
    },
    {
      id: "grid",
      label: "Zero-filled zone-hour grid",
      kind: "data",
      facts: [
        "265 zones × 8,784 hours = 2,327,760 curated rows.",
        "Zero-filled where a zone had no pickups.",
      ],
    },
    {
      id: "features",
      label: "Lag, calendar, weather features",
      kind: "tool",
      facts: [
        "Everything on a feature row precedes the prediction instant — no leakage.",
        "Permutation importance: lag_168 (0.80) > lag_24 (0.64) > lag_1 (0.55).",
      ],
    },
    {
      id: "gbm",
      label: "Tuned GBM · mean + p90 twin",
      kind: "model",
      facts: [
        "Served gbm_tuned: MAE 4.676 on the Oct–Dec holdout — −28.3% vs same-hour-yesterday.",
        "p90 band covers 90.8% of outcomes; sparse N/A zones under-cover at 84.7%.",
      ],
    },
    {
      id: "serving",
      label: "Served three-file bundle",
      kind: "output",
      facts: [
        "Persisted to reports/models/serving/ and served by the showcase API.",
        "Live endpoint verified: POST forecast returns prediction plus p90.",
      ],
    },
  ],
  edges: [
    { id: "tlc-join", source: "tlc", target: "join", kind: "task", label: "trips" },
    { id: "noaa-join", source: "noaa", target: "join", kind: "task", label: "weather" },
    { id: "join-grid", source: "join", target: "grid", kind: "result", label: "zone-hour rows" },
    { id: "grid-features", source: "grid", target: "features", kind: "task", label: "featurise" },
    { id: "features-gbm", source: "features", target: "gbm", kind: "task", label: "fit + tune" },
    { id: "gbm-serving", source: "gbm", target: "serving", kind: "result", label: "model bundle" },
  ],
} as const satisfies DiagramSpec;
