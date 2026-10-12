# NOAA GHCN-Daily

- **Canonical source:** https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861
- **Direct files:** `https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/USW00094728.csv.gz`
  (per-station CSV, GHCN-Daily format documented at the source)
- **License/terms:** Public domain (US Government work).
- **Used by:** Project 07 (weather join key for NYC: Central Park station
  `USW00094728`)

## Snapshot policy

Per-station files are updated in place as observations are quality-controlled.
The pipeline pins the file's sha256 in `scripts/fetch_noaa.py`; mismatch fails
loudly and this card is updated deliberately.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-12 |
| Station | USW00094728 (CENTRAL PARK, NY US) |
| Elements used | PRCP (precipitation, tenths of mm), SNOW, TMAX/TMIN (tenths °C) |
| Format | CSV.gz, GHCN-Daily by-station layout |

## Access

```bash
uv run python docs/data-registry/scripts/fetch_noaa.py --dest data/07/raw/noaa
```

## Notes

- Column layout (by-station files):
  `station, date, element, value, mflag, qflag, sflag, obs_time`.
- `qflag` non-empty ⇒ observation failed quality control; pipeline treats it
  as missing (see Project 07 DESIGN.md).
