import type { DiagramSpec } from "./types";

// Facts: projects/11-data-engineering/{README.md,reports/metrics.json}.
export const ENGINE_BENCHMARK_SPEC = {
  id: "11-engine-benchmark",
  title: "One dataset, four engines, ten tasks — parity before timing",
  direction: "LR",
  canvasHeight: 480,
  nodes: [
    {
      id: "dataset",
      label: "NYC TLC yellow taxi · January 2024",
      kind: "source",
      facts: [
        "2,964,624 trips in the sha256-pinned parquet snapshot.",
        "Derived layouts: a 157 MB CSV and a 31-way hive-partitioned parquet directory.",
      ],
    },
    {
      id: "pandas",
      label: "pandas 2.x",
      kind: "tool",
      facts: [
        "Ladder total 2.99 s; CSV parsing alone is 1.17 s.",
        "The baseline every speedup is measured against.",
      ],
    },
    {
      id: "polars",
      label: "Polars lazy",
      kind: "tool",
      facts: [
        "Ladder total 0.16 s — geomean ×19.2 vs pandas.",
        "Fastest on 9 of 10 tasks; sub-linear log-log growth (0.44–0.76).",
      ],
    },
    {
      id: "duckdb",
      label: "DuckDB SQL",
      kind: "tool",
      facts: [
        "Ladder total 0.22 s — geomean ×14.9 vs pandas.",
        "Wins the sorted distinct rollup; sub-linear growth (0.31–0.65).",
      ],
    },
    {
      id: "sqlite",
      label: "sqlite3 stdlib",
      kind: "tool",
      facts: [
        "40.55 s total — the load-into-memory conversion tax, timed honestly.",
        "Every SQL task parity-checked; write_parquet honestly n/a, not faked.",
      ],
    },
    {
      id: "tasks",
      label: "Ten tasks, one contract",
      kind: "data",
      facts: [
        "Read, group-by, join, window, filter, strings, sort, write, partitioned read.",
        "39 timed cells: median of 5 warm untraced runs + a tracemalloc pass + fresh-process RSS probes.",
      ],
    },
    {
      id: "parity",
      label: "Canonical-result parity gate",
      kind: "gate",
      facts: [
        "Counts, keys and dates exact, floats within 1e-5 — a hard failure gate.",
        "Caught 1,658 hidden trips: pandas read the zone CSV's literal \"N/A\" as missing.",
      ],
    },
    {
      id: "compared",
      label: "Compared + timed",
      kind: "output",
      facts: [
        "Per-task map: 6–18× apart on parquet IO, 29–44× on CSV, group-by and window work.",
        "Full ladder: 2.99 s pandas / 0.16 s Polars / 0.22 s DuckDB / 40.55 s sqlite.",
      ],
    },
  ],
  edges: [
    { id: "dataset-pandas", source: "dataset", target: "pandas", kind: "task", label: "same snapshot" },
    { id: "dataset-polars", source: "dataset", target: "polars", kind: "task", label: "same snapshot" },
    { id: "dataset-duckdb", source: "dataset", target: "duckdb", kind: "task", label: "same snapshot" },
    { id: "dataset-sqlite", source: "dataset", target: "sqlite", kind: "task", label: "same snapshot" },
    { id: "pandas-tasks", source: "pandas", target: "tasks", kind: "task", label: "10 tasks" },
    { id: "polars-tasks", source: "polars", target: "tasks", kind: "task", label: "10 tasks" },
    { id: "duckdb-tasks", source: "duckdb", target: "tasks", kind: "task", label: "10 tasks" },
    { id: "sqlite-tasks", source: "sqlite", target: "tasks", kind: "task", label: "10 tasks" },
    { id: "tasks-parity", source: "tasks", target: "parity", kind: "result", label: "canonical rows" },
    { id: "parity-compared", source: "parity", target: "compared", kind: "result", label: "gate passed" },
  ],
} as const satisfies DiagramSpec;
