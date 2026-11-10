# 11 — Data Engineering: pandas vs Polars vs DuckDB vs sqlite

## Headline — median wall time per task (s)

| task | pandas | Polars | DuckDB | sqlite | Polars x | DuckDB x | sqlite x | fastest |
|---|---|---|---|---|---|---|---|---|
| read_parquet | 0.044 | 0.002 | 0.003 | 4.869 | x18.0 | x15.4 | x0.0 | Polars |
| read_csv | 1.165 | 0.040 | 0.077 | 5.753 | x29.4 | x15.2 | x0.2 | Polars |
| groupby | 0.374 | 0.009 | 0.010 | 5.179 | x40.7 | x36.2 | x0.1 | Polars |
| join | 0.242 | 0.010 | 0.010 | 3.650 | x25.3 | x23.8 | x0.1 | Polars |
| window | 0.341 | 0.008 | 0.009 | 5.882 | x43.5 | x38.4 | x0.1 | Polars |
| filter | 0.048 | 0.004 | 0.012 | 1.947 | x11.0 | x4.1 | x0.0 | Polars |
| strings_groupby | 0.149 | 0.006 | 0.006 | 4.212 | x25.1 | x25.0 | x0.0 | Polars |
| distinct_sort | 0.075 | 0.007 | 0.005 | 3.866 | x11.4 | x14.3 | x0.0 | DuckDB |
| write_parquet | 0.500 | 0.074 | 0.083 | n/a | x6.7 | x6.0 | n/a | Polars |
| partitioned_read | 0.048 | 0.004 | 0.006 | 5.190 | x13.3 | x7.9 | x0.0 | Polars |

## Memory — peak RSS per task (MB)

| task | pandas | Polars | DuckDB | sqlite |
|---|---|---|---|---|
| read_parquet | 549 MB | 200 MB | 178 MB | 1244 MB |
| read_csv | 901 MB | 424 MB | 312 MB | 1520 MB |
| groupby | 718 MB | 316 MB | 255 MB | 993 MB |
| join | 945 MB | 305 MB | 220 MB | 460 MB |
| window | 798 MB | 250 MB | 220 MB | 630 MB |
| filter | 564 MB | 224 MB | 207 MB | 396 MB |
| strings_groupby | 662 MB | 302 MB | 202 MB | 533 MB |
| distinct_sort | 572 MB | 221 MB | 193 MB | 422 MB |
| write_parquet | 577 MB | 529 MB | 633 MB | n/a |
| partitioned_read | 558 MB | 203 MB | 184 MB | 1311 MB |

## IO tasks — cold → warm (s)

| IO task | pandas cold → warm | Polars cold → warm | DuckDB cold → warm | sqlite cold → warm |
|---|---|---|---|---|
| read_parquet | 0.072 → 0.044 | 0.005 → 0.002 | 0.005 → 0.003 | 4.800 → 4.869 |
| read_csv | 1.229 → 1.165 | 0.048 → 0.040 | 0.080 → 0.077 | 5.820 → 5.753 |
| write_parquet | 0.500 → 0.500 | 0.058 → 0.074 | 0.111 → 0.083 | n/a |
| partitioned_read | 0.076 → 0.048 | 0.006 → 0.004 | 0.007 → 0.006 | 5.227 → 5.190 |

## Scalability — median time by seeded size (s)

| task | engine | 1M | 3M | 10M | log-log slope |
|---|---|---|---|
| read_csv | pandas | 0.395 | 2.226 | 4.028 | 1.00 |
| read_csv | Polars | 0.020 | 0.036 | 0.116 | 0.76 |
| read_csv | DuckDB | 0.062 | 0.073 | 0.128 | 0.31 |
| read_csv | sqlite | 1.931 | 5.771 | 19.4 | 1.00 |
| groupby | pandas | 0.115 | 0.337 | 1.146 | 1.00 |
| groupby | Polars | 0.006 | 0.010 | 0.031 | 0.73 |
| groupby | DuckDB | 0.005 | 0.008 | 0.020 | 0.63 |
| groupby | sqlite | 2.136 | 6.852 | 26.4 | 1.09 |
| join | pandas | 0.083 | 0.234 | 0.794 | 0.98 |
| join | Polars | 0.008 | 0.011 | 0.035 | 0.67 |
| join | DuckDB | 0.005 | 0.007 | 0.016 | 0.52 |
| join | sqlite | 1.169 | 3.611 | 12.1 | 1.01 |
| window | pandas | 0.116 | 0.341 | 1.162 | 1.00 |
| window | Polars | 0.005 | 0.006 | 0.013 | 0.44 |
| window | DuckDB | 0.006 | 0.008 | 0.016 | 0.46 |
| window | sqlite | 2.169 | 7.090 | 26.2 | 1.08 |
| filter | pandas | 0.018 | 0.053 | 0.176 | 0.99 |
| filter | Polars | 0.005 | 0.005 | 0.014 | 0.47 |
| filter | DuckDB | 0.003 | 0.006 | 0.013 | 0.65 |
| filter | sqlite | 0.643 | 1.936 | 6.472 | 1.00 |

## By engine

- pandas: total median time 2.99s, geomean speedup vs pandas x1.0
- Polars: total median time 0.16s, geomean speedup vs pandas x19.157
- DuckDB: total median time 0.22s, geomean speedup vs pandas x14.886
- sqlite: total median time 40.55s, geomean speedup vs pandas x0.035

Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, `reports/evaluation_metadata.json`.
