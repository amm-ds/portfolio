# Bike Sharing (UCI — Capital Bikeshare, hourly)

- **Canonical source:** https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip
  (UCI dataset 275; hourly and daily rental counts with weather and calendar
  context; Project 12 consumes `hour.csv` only, pinned by the zip's sha256
  below)
- **License/terms:** free for research and demonstration use; cite Fanaee-T,
  H. and Gama, J. (2013), "Event labeling combining ensemble detectors and
  background knowledge", *Progress in Artificial Intelligence* 2(2–3).
- **Used by:** Project 12 (tabular ML & deep learning lifecycle — real-data
  primary track)
- **Size:** 17,379 hourly records × 13 columns (season, year, month, hour,
  holiday, weekday, workingday, weather situation, temperature, feels-like,
  humidity, wind speed, rental count); 2011–2012 Capital Bikeshare system,
  Washington D.C.

## Snapshot policy

Fetched at prepare time and verified against the sha256 below; the prepared
frame is checksummed again into the project's DatasetContract. A seeded
synthetic twin remains the CI path so tests never touch the network.

| Field | Value |
|---|---|
| Snapshot date | 2026-11-04 |
| Format | zip (CSV inside; `hour.csv` consumed) |
| SHA-256 | `b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401` |
| Split used | time-based: final ~8 weeks held out as the scored-once test window |

## Schema mapping (Project 12)

| UCI column | Project role |
|---|---|
| season, mnth, hr, weekday | calendar features (hr/weekday → cyclical encodings) |
| holiday, workingday | calendar binary features |
| weathersit | ordinal weather situation |
| temp, atemp, hum, windspeed | numeric weather features |
| cnt | target (rentals per hour) |
| instant, dteday, yr, casual, registered | dropped (`instant`/`dteday` are keys; `casual`+`registered` sum to `cnt` — using them is target leakage) |
