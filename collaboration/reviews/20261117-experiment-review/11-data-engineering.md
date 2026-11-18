# 11 · Data engineering (pandas, Polars, DuckDB, sqlite): technical review

## Verdict
A disciplined engine benchmark: one correctness contract before any timing counts, pinned data, and an explicit "n/a" where sqlite cannot write parquet. Ready, with one methodological note on warm and cold timings.

## Architecture
- Ten tasks over 2,964,624 NYC TLC rows, four engines, one canonical-result contract. The parity-before-timing rule is the right design.
- Synthetic CI track keeps the benchmark runnable without the download. Good.

## Results vs benchmarks and SOTA
- The field standard for analytics engine comparison is ClickBench (**verify** the current methodology and whether the repo's tasks map to it). Stating the mapping would strengthen the card.
- Speedups: Polars 6–18×, DuckDB similar. Consistent with the public picture of columnar in-process engines.

## Metrics and statistics
- Median of 5 warm repeats plus a tracemalloc pass and fresh-process probes. Warm-only timings can hide cold-start cost; the copy should say the headline is warm.
- No intervals on medians. Show min and max (or IQR) per cell in the results table.
- Ratio claims ("19x") come from medians; say so.

## Code and tests
- 8 test files. Confirm each task's parity check is tested against a deliberately wrong engine output (a negative test).

## Visuals
- `task_times_dotplot`, `speedup_overview`, `normalized_heatmap`: appropriate. Add the sqlite gap as its own legend entry, not only as absent bars.

## Copy and articles
- Short copy "Polars 19x, DuckDB 15x pandas" is the ladder total; check the total row matches the table (the README table lists per-task speedups, 6–43×).
- Distinguish the ladder total from per-task speedups in one sentence.

## Kimi refinement tasks
1. (major) Show spread (IQR or min/max) per cell beside the medians.
2. (major) Add a negative parity test with a deliberately wrong engine result.
3. (minor) Reconcile the "19x / 15x" ladder total with the table and say what it is.
4. (minor) Map the tasks to ClickBench where possible (**verify**).
