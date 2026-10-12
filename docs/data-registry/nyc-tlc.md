# NYC TLC Trip Records

- **Canonical source:** https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- **Direct files:** `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`
  (CloudFront mirror linked from the TLC page; pattern verified October 2026)
- **License/terms:** NYC TLC terms of use; free, anonymous download, no account.
- **Used by:** Project 07 (Urban Mobility Demand Intelligence)
- **Bounded slice (laptop-friendly):** 12 consecutive months of yellow-taxi
  Parquet (monthly files, ~100–150 MB each compressed).

## Snapshot policy

Monthly files are published with ~2 months delay. This registry pins the months
used by the pipeline in `scripts/fetch_tlc.py` (month list + checksum
verification via `portfolio_core.io.fetch`). If the upstream republishes a
file, the checksum gate fails loudly and this card is updated deliberately
(snapshot date below).

| Field | Value |
|---|---|
| Snapshot date | 2026-10-12 |
| Months used | 2024-01 … 2024-12 (yellow) |
| Zones | all taxi zones (zone lookup joined separately) |
| Format | Parquet (snappy) |

## Access

```bash
uv run python docs/data-registry/scripts/fetch_tlc.py --months 2024-01 2024-12 --dest data/07/raw/tlc
```

## Notes

- Zone/location lookup table:
  `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv`
- Trip data dictionary:
  https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf
