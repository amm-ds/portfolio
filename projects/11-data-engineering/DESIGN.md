# DESIGN — Data Engineering (11)

## Requirements

1. Benchmark three dataframe engines — pandas 2.x, Polars (lazy), DuckDB
   (SQL) — on the same 8 tasks behind one task contract, each task returning
   a canonical, cross-engine comparable result.
2. Real track on the NYC TLC yellow-taxi January 2024 snapshot (public
   parquet, same snapshot family the data registry pins for project 07);
   sha256-pinned fetch; derived CSV and hive-partitioned parquet layout for
   the IO tasks.
3. CI fast path: a seeded synthetic generator producing the same schema —
   the whole synthetic benchmark runs in ~15 s with the full protocol.
4. Per task x engine: median warm wall time (repeated, seeded), cold read
   time for IO tasks (fresh subprocess), peak RSS (fresh-subprocess high-water
   mark) and tracemalloc peak; speedup vs pandas computed from medians.
5. Deterministic modulo timing noise: seeded data, a determinism gate that
   fails a cell loudly when any repeat's canonical result fingerprint drifts,
   hardware + version metadata recorded next to the numbers (08's convention).
6. Artifacts: `reports/metrics.json`, `reports/evaluation_metadata.json`,
   `reports/report.html` (shared EvalReport builder, embedded figures),
   4 figures in both showcase JSON and docs HTML, tests green with `-n 2`.

## Data source decision

| Decision | Options | Choice | Why |
|---|---|---|---|
| Real slice | TLC full year; one month; sampled subset | **One month: yellow 2024-01** | ~3.0 M rows / 50 MB compressed is the largest slice that keeps every engine's task in seconds and the whole benchmark in minutes on a laptop; a month also gives the per-day group-by and the 31-way partitioned read natural meaning. It is the exact snapshot family the registry pins for 07 (`registry/nyc-tlc-yellow-2024-01.dvc`: same URL, byte size and etag), so the dataset card resolves for both projects. |
| Fetch pinning | etag/md5 (registry style); sha256 | **sha256 in `params.yaml` + `fetch.py`** | sha256 is verified by `portfolio_core.io.fetch` on download *and* re-verified on every real-track load — a republished upstream file fails loudly instead of benchmarking the wrong data. |
| Working schema | All 20 raw columns; 6-column projection | **6-column projection** (`tpep_pickup_datetime`, `PU/ DOLocationID`, `passenger_count`, `trip_distance`, `fare_amount`) | The tasks need these; the projection keeps the derived CSV at ~145 MB instead of ~700 MB and every engine reads identical bytes. The projection is done once, in `fetch-data`, so task code never diverges between tracks. |
| Zones lookup | Shapefile boundaries; zone CSV | **`taxi_zone_lookup.csv`** (sha-pinned, same CloudFront mirror family) | The join task needs LocationID -> Borough/Zone; the CSV is the canonical lookup (the shapefile is only for choropleths, which 07 owns). |
| CSV for the read task | Reuse upstream CSV; derive from parquet | **Derived `trips.csv`** | Upstream publishes no CSV for this month with the 6-column projection; deriving it once from the pinned parquet guarantees every engine reads byte-identical, reproducible input. |
| Partitioned layout | Single-file reads; per-day hive dirs | **`partitioned/day=NN/part-0.parquet` (31 parts)** | Mirrors how lakehouse data actually lands; exercises multi-file discovery + predicate-relevant partition columns in all three engines (pyarrow dataset, `scan_parquet` glob, `read_parquet(..., hive_partitioning=true)`). |

## Task decisions (dimensions adapted from the canonical duckdb/polars/h2o
group-by benchmark family)

| Task | Category | Dimension covered | Canonical result |
|---|---|---|---|
| `read_parquet` | io | Parquet read + reduce | row count + fare sum |
| `read_csv` | io | CSV read, typed timestamps (pandas `parse_dates` / polars inference / `read_csv_auto`) | row count + fare sum |
| `groupby` | compute | Per-day group-by aggregation: trips, total fare, mean distance, mean passengers | 31 rows |
| `join` | compute | Star join to zone lookup, aggregate by borough | 5-6 rows |
| `window` | compute | Top-5 pickup zones per day — `row_number` / group-cumcount / sorted `over` with the same deterministic tiebreak (trips desc, zone asc) | 155 rows |
| `filter` | compute | Filtered scan / predicate pushdown: `fare_amount > 50 AND trip_distance > 10` | row count + fare sum |
| `write_parquet` | io | Native write path: `to_parquet` / `sink_parquet` / `COPY ... TO (FORMAT PARQUET)`; output row count read back with pyarrow | row count (+ bytes as non-comparable detail) |
| `partitioned_read` | io | Out-of-core-style multi-file read of the 31 per-day files | row count + fare sum |

Rejected dimensions: multi-join queries over several tables (the yellow-taxi
slice has one natural lookup), UDFs (not comparable across engines), wide
string-heavy group-bys (the projection has one timestamp and no free-text
column; forcing one in would not match the real track).

## Engine decisions

| Decision | Options | Choice | Why |
|---|---|---|---|
| pandas strings | `infer_string` / `dtype_backend="pyarrow"` / numpy-backed default | **numpy-backed default** | The benchmark reads typed parquet/CSV columns — the pyarrow-string option only affects object columns, of which the working schema has none. Default pandas is also what a client is most likely to run. |
| Polars execution | eager `read_parquet`; lazy scans | **lazy scans + `collect` at the boundary** | The idiomatic Polars path; the whole plan (read + compute) is what gets timed, matching how the engine is actually used. |
| DuckDB interface | in-process SQL strings; relational API; `duckdb` module functions | **parameterized SQL over one in-memory connection** | One connection per cell; `read_parquet` / `read_csv_auto` table functions keep SQL portable across file layouts; parameters avoid path-escaping hazards. |
| Parquet engines | pandas `engine="fastparquet"`; `engine="pyarrow"` | **pyarrow** | Already the repo's parquet pairing; consistent with the pyarrow metadata reads the harness uses. |
| Result interchange | per-engine JSON normalization; polars as the single interchange | **polars DataFrame at the task boundary + `canonical_rows`** | Every engine can emit polars (pandas `from_pandas`, DuckDB `to_arrow_table`); canonicalization (dates -> ISO, floats rounded, rows sorted) lives in exactly one place. |

## Metrics & protocol decisions

| Decision | Options | Choice | Why |
|---|---|---|---|
| Warm timing | single run; mean; median of repeats | **median of `repeats` in-process runs** | Median resists scheduler noise; repeats are few because IO tasks dominate runtime. |
| Cold reads | in-process first run; fresh subprocess | **fresh subprocess per IO cell** (`python -m data_engineering.cold`) | A new interpreter also pays import + library-init cost — the honest "cold" number. The OS page cache is *not* dropped (not portable without root); the limits section says so. |
| Peak RSS | `tracemalloc`; `resource` deltas in-process; fresh-process high-water | **fresh-process `ru_maxrss` high-water** (probes) + tracemalloc as a second, Python-side signal | tracemalloc misses native allocations (Polars/DuckDB allocate mostly natively — it would systematically under-report exactly the engines it should be measuring fairly); in-process `ru_maxrss` deltas under-report every cell after the first high because the counter is a lifetime maximum. A fresh process owns its memory: the high-water mark is attributable to the cell alone. |
| Speedup | mean-of-ratios; ratio-of-medians | **ratio of medians, per task; geomean across tasks** | The standard way to read engine benchmarks; the per-task ratio stays honest when one engine is 20x faster on one task. |
| Determinism | trust; recompute | **canonical-result gate** | Every repeat's and every probe's canonical rows must match the first repeat's, in-process and cross-process — ints, strings and dates exactly, floats within 1e-5 relative of the 6-significant-digit canonical form: a parallel engine legitimately reorders float summation between runs, and a group sum can sit within an ulp of a rounding cliff (one display bin), so exact float equality would flag noise, not drift. Structural changes (counts, keys, row order) still fail loudly — the gate caught both failure shapes on the real track before this wording settled. |
| Failure modes | skip failed cells | **fail loudly** | Checksum mismatch, missing artifact, probe failure, non-deterministic result: all raise. There is no partial benchmark. |

## Options considered for the harness shape

- **One subprocess per repeat** (timing + memory both from fresh processes):
  rejected — process-spawn overhead (hundreds of ms) would dominate the
  sub-second compute tasks and bias them toward whichever engine imports
  slowest. Warm timing stays in-process where the engines keep their caches.
- **psutil sampling thread**: rejected — not a dependency; `resource` covers
  the fresh-process peak; in-process tracemalloc covers the Python side.
- **Separate benchmark scripts per engine**: rejected — the single harness +
  task registry is what makes parity a testable contract instead of a hope.

## Reproduce

```bash
cd projects/11-data-engineering
uv run python -m data_engineering.cli fetch-data          # real track (network, pinned)
uv run python -m data_engineering.cli evaluate            # real benchmark -> reports/
uv run python -m data_engineering.cli evaluate --synthetic  # CI fast path (~15 s)
uv run pytest -q                                          # offline suite
```
