# NAB (Numenta Anomaly Benchmark)

- **Canonical source:** https://github.com/numenta/NAB (Numenta research
  benchmark; citation: Ahmad, Lavin, Purdy & Agha (2017), "Unsupervised
  real-time anomaly detection for streaming data", *Neurocomputing*
  262:134–147)
- **Direct files:** per-series CSVs under `data/realAWSCloudwatch/`,
  `data/realTraffic/`, `data/realKnownCause/` plus
  `labels/combined_windows.json`, each fetched individually with sha256
  verification via `portfolio_core.io.fetch` (see
  `data-registry/imports/nab.json` for the import-url manifest)
- **License/terms:** research benchmark; cite the Ahmad et al. (2017) paper in
  derived work
- **Used by:** Project 03 — **primary real-data track** (12 series spanning
  the three families above; the seeded synthetic telemetry generator remains
  the clearly-labelled CI / fast path)
- **Size:** 12 series, ~4 000–22 700 points each (`timestamp,value`, 5- or
  30-minute sampling), 31 labelled anomaly windows total (17 overlapping the
  scored test portions)

## Snapshot policy

| Field | Value |
|---|---|
| Snapshot date | 2026-10-15 |
| Format | CSV per series (`timestamp,value`), labels as JSON windows |
| Checksums | pinned per file in `projects/03-anomaly-detection/src/anomaly_detection/nab.py` (`NAB_SERIES`) and mirrored in `data-registry/imports/nab.json` |

## Access

Via Project 03's `nab` stage / `anomaly_detection.nab` module (fetch +
checksum + rolling features + event-based metrics: PR-AUC, range-F1 with
window matching, alert-budget curve). Headline results on the current
snapshot: PR-AUC 0.527, range-F1 0.157 (16/17 events detected at 10.7%
range precision, 1 609 alerts) — see the project story for the honest
real-vs-synthetic delta narrative.
