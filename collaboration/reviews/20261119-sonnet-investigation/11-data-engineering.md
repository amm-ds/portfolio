# 11 Data engineering: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Ten tasks over 2.96M NYC taxi trips (2,964,624 rows per the experiment review), parity-checked on pandas, Polars, DuckDB and stdlib sqlite: Polars 19x, DuckDB 15x pandas (ladder total); sqlite about 29x slower after file conversion; 1M-10M tracks show sub-linear scaling (log-log slopes 0.31-0.76 for Polars and DuckDB; 0.98-1.09 for pandas and sqlite); 39/39 measured cells passed the canonical gate; median of 5 warm repeats; tracing outside the timed region; parity found 1,658 hidden N/A-borough trips. The 10M track is seeded synthetic. Source: `projects/11-data-engineering/story.yaml`; metrics `projects/11-data-engineering/reports/metrics.json`.
- Experiment review notes: no spread shown per cell; headline is warm; ladder total vs per-task speedups (6-43x) should be distinguished.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | ClickBench distinguishes true cold runs (restart) from "lukewarm" (OS page cache cleared only); disputes over submissions that left caches on or restarted per iteration; rankings fragile to small setup changes. Our headline is warm; a cold column does not exist. | SEC (issue threads and a competitor's blog) | S36, S37 |
| G2 | DuckDB's own guide: fair system-to-system benchmarking is hard; use the latest version; TPC-derived data is not an official TPC result. Ibis runs Polars LazyFrames without the streaming engine; Coiled shows the winner depends on scale and hardware. | SEC | S38, S39, S40 |
| G3 | Versions: I did not read which engine versions the repo pins and whether Polars streaming is used. Cannot compare to S39 without that. | GAP (repo detail) | none |
| G4 | Real-data scaling to 10M rows: the roadmap names it; no source needed. | n/a | none |

## Candidate improvements
**A. Add cold-start timings and per-cell spread from the existing harness.**
- Method: fresh-process first-run timing per task per engine (the harness already has fresh-process probes per the experiment review), reported separately from the warm median; add min/max or IQR per cell.
- Reference: https://github.com/ClickHouse/ClickBench/issues/656 (S36) for the cold/lukewarm distinction.
- Cost: compute only, about 1 day.
- Stop condition: OS cache cannot be dropped without privileges; then label the number "first run, OS cache warm" and do not call it cold.

**B. Pin and publish engine versions and Polars mode; add a one-line mapping to a TPC-H-style or ClickBench-style query.**
- Method: record versions, Polars engine setting (lazy, streaming or not), file format and thread count in the metrics `_meta`; no new timings.
- Reference: https://ibis-project.org/posts/ibis-bench/ (S39); https://duckdb.org/docs/current/guides/performance/benchmarks (S38).
- Cost: under 1 day.
- Stop condition: pinned versions differ across tasks; rerun that task.

**C. Real 10M-row track from additional TLC months.**
- Method: concatenate real months to reach 10M rows; same parity gate.
- Reference: none needed; roadmap item.
- Cost: download size and compute; owner OK for the download.
- Stop condition: parity failures on schema drift between months; document and stop.

**D. Memory and spill behaviour at 10M.**
- Method: peak RSS per engine per task via the existing tracemalloc/fresh-process probes, plotted against size.
- Reference: https://docs.coiled.io/blog/tpch (S40) for scale context.
- Cost: compute only.
- Stop condition: probe overhead changes timings; keep memory runs separate.

## Ranked recommendation
1. A (cold runs and spread): addresses the one known methodological note.
2. B (version and mode disclosure): near-free.
3. C (real 10M), then D.

## Queries used (standard, 2026-11-18)
- "ClickBench methodology benchmark pitfalls database benchmarking hygiene cold hot runs"
- "DuckDB Polars benchmark methodology TPC-H H2O db-benchmark scale factor fair comparison"
