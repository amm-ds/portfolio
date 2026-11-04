# 11 — Data Engineering: pandas vs Polars vs DuckDB

A dataframe-engine benchmark built the way the portfolio builds everything:
pinned public data, one task contract every engine must satisfy, a seeded
CI track, and numbers that re-run from the README.

- **Domain:** data engineering (engine benchmarking)
- **Data:** NYC TLC yellow taxi, January 2024 (2,964,624 trips, real parquet,
  sha256-pinned — the same snapshot family the registry pins for 07) + a
  seeded synthetic track for CI
- **Status:** working showcase
- **Runtime:** real benchmark ≈ **42 s** for 8 tasks × 3 engines (median of
  5 warm repeats + fresh-process probes); synthetic CI track ≈ **15 s**

## Problem

Every data platform eventually weighs migrating from pandas. Public
benchmarks rarely survive scrutiny: different queries per engine, no
correctness check, no pinned data, numbers from an unknown machine. This
project answers with a measured map — eight analytics-shaped tasks run on
**pandas 2.x**, **Polars (lazy)**, and **DuckDB (SQL)** behind one contract:
every task must return the same canonical result on every engine before any
timing counts.

## Design summary

See [DESIGN.md](DESIGN.md) for the full requirements/options/decision record.

- `fetch.py` — sha256-pinned download of the January-2024 snapshot + zone
  lookup (re-verified on every real-track run); derives the prepared layout:
  6-column projection, `trips.parquet`, `trips.csv` (145 MB), and a
  31-way hive-partitioned parquet directory.
- `synthetic.py` — the seeded CI track: same schema from one numpy
  generator, byte-stable to the checksum.
- `engines.py` — the three adapters (pandas/pyarrow reads, Polars lazy
  scans, DuckDB SQL over `read_parquet`/`read_csv_auto`/`COPY`).
- `tasks.py` — the registry: 8 tasks × 3 engines — parquet read, CSV read,
  per-day group-by, zone join, top-N-per-day window, filtered scan
  (predicate pushdown), parquet write, 31-file partitioned read. Each
  returns canonical rows (dates ISO, 6 significant digits, canonically
  sorted).
- `harness.py` + `cold.py` — the protocol: median of `repeats` warm
  in-process runs under tracemalloc; one fresh-subprocess probe per
  task×engine cell for true peak RSS (and the cold read for IO tasks);
  a determinism gate between every pair of runs (counts/keys/dates exact,
  floats within 1e-5 — parallel summation reorder is noise, structural
  drift fails loudly).
- `metrics.py` / `figures.py` / `report.py` — `metrics.json`,
  `evaluation_metadata.json` (versions + hardware, 08's convention), four
  figures (runtime, memory, speedup, IO cold/warm) in showcase JSON + docs
  HTML, and the shared `EvalReport` HTML + `results.md`.
- `cli.py` — typer: `fetch-data`, `evaluate` (`--synthetic` for CI),
  `build-report` (offline rebuild from committed artifacts).

## Results (real run: NYC TLC 2024-01, 2,964,624 rows, seed 42)

Median wall time per task (seconds; × = speedup vs pandas; the bold row is
the ladder total). Full record in `reports/metrics.json` and
`reports/results.md`; the evaluation protocol and hardware context in
`reports/evaluation_metadata.json`.

| task | pandas | Polars | DuckDB | Polars × | DuckDB × |
|---|---|---|---|---|---|
| read_parquet | 0.014 | 0.003 | 0.003 | 5.4 | 4.7 |
| read_csv | 1.444 | 0.040 | 0.064 | 36.4 | 22.6 |
| groupby | 1.517 | 0.010 | 0.014 | 158.1 | 111.5 |
| join | 0.205 | 0.010 | 0.010 | 20.6 | 21.3 |
| window | 1.491 | 0.011 | 0.012 | 137.6 | 122.4 |
| filter | 0.018 | 0.005 | 0.005 | 3.9 | 3.9 |
| write_parquet | 0.277 | 0.056 | 0.050 | 4.9 | 5.5 |
| partitioned_read | 0.017 | 0.004 | 0.005 | 4.7 | 3.3 |
| **total / geomean** | **4.98** | **0.14** | **0.16** | **×17.3** | **×14.7** |

Fresh-process peak RSS per task: pandas 446–797 MB (join worst), Polars
196–428 MB, DuckDB 177–455 MB; on the write task all three tie around
428–455 MB — the frame has to exist somewhere. Cold reads (fresh
interpreter; the OS page cache is not dropped): pandas's CSV read is 1.15 s
cold vs 1.44 s warm, everything else within tens of milliseconds of warm.

Key findings:

- **The map matters more than the mean.** Per-task speedups run from 3–5x
  (parquet IO — at this size the page cache, not the engine, sets the
  price) to 111–158x on the group-by and window tasks, where pandas builds
  Python-object intermediates (`.dt.date`, per-group `cumcount`).
- **CSV parsing is pandas's heaviest tax**: 1.44 s of its 4.98 s ladder —
  the single strongest task-level case for Polars (×36).
- **The parity gate earned its keep.** pandas's default CSV parsing reads
  the zone lookup's literal `"N/A"` borough as missing, and `groupby` then
  silently drops those rows — 1,658 trips hidden until the three-engine
  comparison failed the cell. Fixed with `keep_default_na=False`; a
  regression test pins it.
- **Exact float equality is the wrong determinism bar.** DuckDB and Polars
  may reorder parallel summation between runs; a 295-trip borough sum sat
  within an ulp of a 6-significant-digit rounding cliff. The gate compares
  counts, keys and dates exactly, and float sums within a 1e-5 band —
  structural drift still fails loudly (the gate caught real drift twice
  while this protocol was being built).
- **Fastest per task:** Polars takes 6 of 8; DuckDB takes the join and
the parquet write.

Figures (`reports/figures/`, JSON + HTML for the showcase API):

- `speedup_vs_pandas` / `runtime_by_task` — the map: per-task speedups and
  medians (log scale), geomean annotated.
- `memory_by_task` — fresh-process peak RSS per task.
- `io_cold_warm` — cold fresh-process reads vs warm medians for the four IO
  tasks.

## Reproduce

```bash
cd projects/11-data-engineering
uv run python -m data_engineering.cli fetch-data            # real track (network, sha-pinned)
uv run python -m data_engineering.cli evaluate              # real benchmark -> reports/ (~42 s)
uv run python -m data_engineering.cli evaluate --synthetic  # CI fast path (~15 s)
uv run python -m data_engineering.cli build-report          # rebuild report.html offline
```

Tests (offline, synthetic track only):

```bash
uv run pytest -q            # or with the CI flags: -n 2 --timeout=600
```

## What this demonstrates for a client

- **Decisions on measured maps, not slogans:** engine choice depends on the
  task mix — the same three engines tie on one task and sit 158x apart on
  another.
- **Correctness before performance:** a timing comparison is only real if
  the engines return the same answer; the parity gate is a hard failure,
  and it caught a genuine data-loss footgun.
- **Honest measurement:** fresh-process memory probes (no cross-task
  charging), median-of-repeats timing, hardware and versions recorded next
  to every number.
- **Reproducibility:** sha256-pinned data, a seeded CI track running the
  full protocol in seconds, determinism gates that fail loudly.

## Roadmap — delivered (retrospective)

- Eight-task contract on pandas / Polars / DuckDB with canonical-result
  parity as a hard gate (geomean ×17.3 / ×14.7 vs pandas).
- Pinned real track (NYC TLC 2024-01, sha256) + derived CSV and partitioned
  layout; seeded synthetic CI track.
- Fresh-process peak-RSS probes and cold IO reads; metadata records
  versions, hardware, and the protocol.

Deferred (engagement-dependent): bigger-than-RAM out-of-core track with a
cold page cache; additional engines (e.g. DataFusion); object-storage IO.
