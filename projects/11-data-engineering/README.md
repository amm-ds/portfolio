# 11 — DataFrame Engines Benchmark: pandas vs Polars vs DuckDB vs sqlite

A dataframe-engine benchmark built the way the portfolio builds everything:
pinned public data, one task contract every engine must satisfy, a seeded
CI track, and numbers that re-run from the README.

- **Domain:** data engineering (engine benchmarking)
- **Data:** NYC TLC yellow taxi, January 2024 (2,964,624 trips, real parquet,
  sha256-pinned — the same snapshot family the registry pins for 07) + seeded
  synthetic tracks for CI and the scalability study
- **Status:** working showcase
- **Runtime:** real benchmark ≈ **8 min** for 10 tasks × 4 engines (39 timed
  cells; median of 5 warm untraced repeats + a tracemalloc pass +
  fresh-process probes); scalability study ≈ **5 min**; synthetic CI track
  ≈ **26 s**

## Problem

Every data platform eventually weighs migrating from pandas. Public
benchmarks rarely survive scrutiny: different queries per engine, no
correctness check, no pinned data, numbers from an unknown machine. This
project answers with a measured map — ten analytics-shaped tasks run on
**pandas 2.x**, **Polars (lazy)**, **DuckDB (SQL)**, and **sqlite3** (Python
stdlib — the engine every install already has) behind one contract: every
task must return the same canonical result on every engine before any
timing counts. sqlite has one honest gap — stdlib sqlite3 cannot write
parquet, so `write_parquet` is n/a there rather than faked.

## Design summary

See [DESIGN.md](DESIGN.md) for the full requirements/options/decision record.

- `fetch.py` — sha256-pinned download of the January-2024 snapshot + zone
  lookup (re-verified on every real-track run); derives the prepared layout:
  8-column projection (`VendorID`/`payment_type` as strings),
  `trips.parquet`, `trips.csv` (157 MB), and a 31-way hive-partitioned
  parquet directory.
- `synthetic.py` — the seeded CI/scalability track: same schema from one
  numpy generator, byte-stable to the checksum.
- `engines.py` — the four adapters (pandas/pyarrow reads, Polars lazy
  scans, DuckDB SQL over `read_parquet`/`read_csv_auto`/`COPY`, sqlite3 SQL
  over a per-call in-memory database loaded via pandas — the load is timed,
  honestly, as the conversion tax).
- `tasks.py` — the registry: 10 tasks × 4 engines — parquet read, CSV read,
  per-day group-by, zone join, top-N-per-day window, filtered scan
  (predicate pushdown), string-categorical rollup (payment_type × vendor),
  sorted distinct rollup, parquet write (sqlite n/a), 31-file partitioned
  read. Each returns canonical rows (dates ISO, 6 significant digits,
  canonically sorted).
- `scalability.py` — the seeded 1M / 3M / 10M study over the five most
  discriminating tasks; per-cell log-log growth slopes committed in
  `metrics.json`.
- `harness.py` + `cold.py` — the protocol: median of `repeats` warm
  in-process runs **without** tracemalloc (the tracer inflates
  allocation-heavy cells and would distort the timed region); one dedicated
  untimed tracemalloc pass per cell (full-protocol runs); one
  fresh-subprocess probe per task×engine cell for true peak RSS (and the
  cold read for IO tasks); a determinism gate between every pair of runs
  (counts/keys/dates exact, floats within 1e-5 — parallel summation
  reorder is noise, structural drift fails loudly).
- `metrics.py` / `figures.py` / `report.py` — `metrics.json`,
  `evaluation_metadata.json` (versions + hardware, 08's convention), five
  figures (dot plot, speedup dot chart, scalability lines, memory lollipop,
  normalized heatmap) in showcase JSON + docs HTML, and the shared
  `EvalReport` HTML + `results.md`.
- `cli.py` — typer: `fetch-data`, `evaluate` (`--synthetic` for CI,
  `--scalability` for the size study), `build-report` (offline rebuild from
  committed artifacts).

## Results (real run: NYC TLC 2024-01, 2,964,624 rows, seed 42)

Median wall time per task (seconds; × = speedup vs pandas; the bold row is
the ladder total). Full record in `reports/metrics.json` and
`reports/results.md`; the evaluation protocol and hardware context in
`reports/evaluation_metadata.json`.

| task | pandas | Polars | DuckDB | sqlite | Polars × | DuckDB × |
|---|---|---|---|---|---|---|
| read_parquet | 0.044 | 0.002 | 0.003 | 4.869 | 18.0 | 15.4 |
| read_csv | 1.165 | 0.040 | 0.077 | 5.753 | 29.4 | 15.2 |
| groupby | 0.374 | 0.009 | 0.010 | 5.179 | 40.7 | 36.2 |
| join | 0.242 | 0.010 | 0.010 | 3.650 | 25.3 | 23.8 |
| window | 0.341 | 0.008 | 0.009 | 5.882 | 43.5 | 38.4 |
| filter | 0.048 | 0.004 | 0.012 | 1.947 | 11.0 | 4.1 |
| strings_groupby | 0.149 | 0.006 | 0.006 | 4.212 | 25.1 | 25.0 |
| distinct_sort | 0.075 | 0.007 | 0.005 | 3.866 | 11.4 | 14.3 |
| write_parquet | 0.500 | 0.074 | 0.083 | n/a | 6.7 | 6.0 |
| partitioned_read | 0.048 | 0.004 | 0.006 | 5.190 | 13.3 | 7.9 |
| **total / geomean** | **2.99** | **0.16** | **0.22** | **40.55** | **×19.2** | **×14.9** |

sqlite's per-task numbers are the honest cost of doing analytics with the
classical engine on file-shaped data: it cannot read parquet or CSV itself,
so every task first loads the file into its in-memory database (timed, by
design). That conversion dominates: sqlite totals 40.55 s for the same
results pandas produces in 2.99 s (geomean ×0.035 — about 29× slower than
pandas), and it peaks at 1.5 GB of RSS on the CSV cell (the frame and the
database coexist). Its one unimplementable task, the parquet write, is
reported as n/a — not faked.

Fresh-process peak RSS per task: pandas 549–945 MB (join worst), Polars
200–529 MB, DuckDB 178–633 MB, sqlite 396–1520 MB (read_csv worst). On the
write task all three applicable engines land within 529–633 MB — the frame
has to exist somewhere. Cold reads (fresh interpreter; the OS page cache is
not dropped): pandas's CSV read is 1.23 s cold vs 1.17 s warm; sqlite's
cold tracks its warm almost exactly (5.82 vs 5.75 s) because the conversion,
not the interpreter startup, is its cost.

Key findings:

- **The map matters more than the mean.** Per-task speedups run from 6–18×
  (parquet IO, where the page cache sets much of the price) to 29–44× on
  CSV, group-by, and window work — one number never answers the engine
  question.
- **Untraced timing changed the record — the tracer was the distortion.**
  With tracemalloc inside the timed region (the first protocol), pandas's
  group-by read 1.52 s; without it, 0.37 s. The wall-time protocol now runs
  repeats untraced and measures the Python-side allocation peak in one
  dedicated untimed pass, so no engine is timed through a profiler.
- **CSV parsing is still pandas's heaviest tax:** 1.17 s of its 2.99 s
  ladder — the single strongest task-level case for Polars (×29).
- **sqlite is the honest classical baseline, not a competitor:** correct on
  every SQL task (window functions included) but linear in the data with a
  large conversion constant — at 10M rows it needs 19.4 s to read the CSV
  where Polars needs 0.12 s.
- **Scalability curves separate the engines by shape, not just height** (see
  `scalability_lines`): pandas and sqlite grow linearly (log-log slope
  0.98–1.09 on every task); Polars (0.44–0.76) and DuckDB (0.31–0.65) grow
  sub-linearly — at 10M rows the group-by costs pandas 1.15 s, Polars
  0.031 s, DuckDB 0.020 s, sqlite 26.4 s.
- **The parity gate earned its keep.** pandas's default CSV parsing reads
  the zone lookup's literal `"N/A"` borough as missing, and `groupby` then
  silently drops those rows — 1,658 trips hidden until the cross-engine
  comparison failed the cell. Fixed with `keep_default_na=False`; a
  regression test pins it.
- **Fastest per task:** Polars takes 9 of 10; DuckDB takes the sorted
  distinct rollup.

Figures (`reports/figures/`, JSON + HTML for the showcase API):

- `task_times_dotplot` — median dot with min/max whiskers per task × engine
  (log scale): the map at a glance, including sqlite's conversion tax.
- `speedup_overview` — dot chart vs the pandas baseline, and vs sqlite for
  the SQL tasks.
- `scalability_lines` — log-log time-vs-size lines per engine on the five
  discriminating tasks (1M / 3M / 10M).
- `memory_lollipop` — fresh-process peak RSS per task × engine.
- `normalized_heatmap` — each task scaled to its fastest engine; the
  write_parquet × sqlite cell is an honest n/a gap.

## Limits

sqlite is the honest classical baseline, not a competitor — correct on every
SQL task but ~29× slower than pandas end-to-end because the file→database
conversion is timed, not hidden. Speedups are this machine's map, not a
universal constant; the out-of-core cold-cache track and further engines are
deferred (roadmap below).

## Reproduce

```bash
cd projects/11-data-engineering
uv run python -m data_engineering.cli fetch-data                # real track (network, sha-pinned)
uv run python -m data_engineering.cli evaluate                  # real benchmark -> reports/ (~8 min)
uv run python -m data_engineering.cli evaluate --scalability    # + 1M/3M/10M study (~5 min)
uv run python -m data_engineering.cli evaluate --synthetic      # CI fast path (~26 s)
uv run python -m data_engineering.cli build-report              # rebuild report.html offline
```

Tests (offline, synthetic track only):

```bash
uv run pytest -q            # or with the CI flags: -n 2 --timeout=900
```

## Common errors

| symptom | cause | fix |
|---|---|---|
| `evaluate` (or `--scalability`/`build-report`) fails on a missing prepared file | the prepared layout (`data/prepared/`, ~157 MB CSV + hive partitions) is derived, not committed | run `uv run python -m data_engineering.cli fetch-data` first (sha256-pinned download + derive, re-verified on every run), or `uv run dvc repro` |

## What this demonstrates for a client

- **Decisions on measured maps, not slogans:** engine choice depends on the
  task mix — the same four engines tie on one task and sit 44× apart on
  another, and the classical engine's conversion tax is quantified, not
  assumed.
- **Correctness before performance:** a timing comparison is only real if
  the engines return the same answer; the parity gate is a hard failure,
  and it caught a genuine data-loss footgun.
- **Honest measurement:** untraced wall-time medians, a separate allocation
  diagnostic, fresh-process memory probes (no cross-task charging),
  hardware and versions recorded next to every number.
- **Reproducibility:** sha256-pinned data, seeded synthetic tracks running
  the full protocol in seconds, determinism gates that fail loudly.

## Roadmap — delivered (retrospective)

- Ten-task contract on pandas / Polars / DuckDB / sqlite3 with
  canonical-result parity as a hard gate (geomean ×19.2 / ×14.9 vs pandas).
- Pinned real track (NYC TLC 2024-01, sha256) + derived CSV and partitioned
  layout; seeded synthetic CI + scalability tracks (1M / 3M / 10M).
- sqlite3 as the stdlib baseline: every SQL task parity-checked, the parquet
  write honestly n/a.
- Fresh-process peak-RSS probes, cold IO reads, untraced timing with a
  dedicated allocation pass; metadata records versions, hardware, and both
  protocols.

Deferred (engagement-dependent): bigger-than-RAM out-of-core track with a
cold page cache; additional engines (e.g. DataFusion); object-storage IO.
