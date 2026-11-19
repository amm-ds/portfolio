# Cold-start timings with per-cell spread

Generated: 2026-11-19T14:32:41.135845+00:00 · 15 cold-measurable cells x 5 fresh-process probes - real-trip bundle.

| task | engine | cold med (s) | spread | warm med (s, committed) | cold/warm |
|---|---|---|---|---|---|
| partitioned_read | duckdb | 0.008 | 0.021 | 0.006 | 1.26 |
| partitioned_read | pandas | 0.078 | 0.013 | 0.048 | 1.62 |
| partitioned_read | polars | 0.007 | 0.002 | 0.004 | 1.96 |
| partitioned_read | sqlite | 5.296 | 0.121 | 5.190 | 1.02 |
| read_csv | duckdb | 0.083 | 0.026 | 0.077 | 1.08 |
| read_csv | pandas | 1.207 | 0.031 | 1.165 | 1.04 |
| read_csv | polars | 0.041 | 0.007 | 0.040 | 1.04 |
| read_csv | sqlite | 5.854 | 0.149 | 5.753 | 1.02 |
| read_parquet | duckdb | 0.006 | 0.002 | 0.003 | 2.03 |
| read_parquet | pandas | 0.074 | 0.012 | 0.044 | 1.67 |
| read_parquet | polars | 0.005 | 0.001 | 0.002 | 1.94 |
| read_parquet | sqlite | 4.827 | 0.101 | 4.869 | 0.99 |
| write_parquet | duckdb | 0.107 | 0.007 | 0.083 | 1.28 |
| write_parquet | pandas | 0.518 | 0.014 | 0.500 | 1.03 |
| write_parquet | polars | 0.067 | 0.017 | 0.074 | 0.91 |

Spread is the max-min across the five cold probes of one cell on one shared machine — read it as run-to-run noise, not a distribution. New files only; committed timing reports untouched.
