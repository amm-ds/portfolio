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

- **Drift observatory:** the scheduled `drift-observatory` workflow scores
  *each newly published month* against Project 07's pinned serving model
  (`mobility.cli drift-check --month YYYY-MM`): the month's file is fetched
  through this card's URL pattern, lightly re-validated, aggregated to the
  zone-hour grain, and scored with the persisted GBM + p90 pair — no
  retraining. A relative MAE regression beyond `drift.tolerance` (default
  15%) against the pinned test-window metrics opens a tracking issue;
  response steps live in
  [docs/runbooks/drift-response.md](../runbooks/drift-response.md).
  Months that are not published yet exit 2 (skip-worthy, no issue).
- Zone/location lookup table:
  `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv`
- Zone boundaries (shapefile, used by Project 07 choropleths):
  `https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip`
  (263 zone polygons, EPSG:2263; checksum-pinned in the pipeline's
  `data/raw/checksums.json`, snapshot 2026-10-15)
- Trip data dictionary:
  https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf
