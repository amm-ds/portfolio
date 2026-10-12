# CVRPLIB — Solomon VRPTW benchmark

- **Canonical source:** https://galgos.inf.puc-rio.br/cvrplib/ (VRPTW → Solomon set)
- **License/terms:** Academic benchmark, free to use with citation
  (Solomon, M. (1987), Operations Research 35(2)).
- **Used by:** Project 06 (routing optimization)
- **Size:** 56 instances × 100 customers, published best-known solutions.

## Snapshot policy

Instance text files are immutable academic artifacts. The pipeline pins each
instance file's sha256 (see `scripts/fetch_cvrplib.py`).

| Field | Value |
|---|---|
| Snapshot date | 2026-10-12 |
| Instance archive | `https://www.sintef.no/globalassets/project/top/vrptw/solomon/solomon-100.zip` (SINTEF TOP backup mirror; the historical `solomonbenchmark.s3.amazonaws.com` mirror 404s as of Oct 2026) |
| Format | Solomon VRPTW text (`.txt`, one file per instance) |

## Access

```bash
uv run python docs/data-registry/scripts/fetch_cvrplib.py --dest data/06/raw
```

## Notes

- Published optima/best-known values ship in `data/06/raw/best_known/` as a
  curated CSV (`instance,best_known`) used by the evaluation stage for the
  gap-% table.
