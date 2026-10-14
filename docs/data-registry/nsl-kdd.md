# NSL-KDD

- **Canonical source:** https://www.unb.ca/cic/datasets/nsl.html (UNB Canadian
  Institute for Cybersecurity — research benchmark)
- **Direct files:** checksum-pinned mirrors of `KDDTrain+.TXT` / `KDDTest+.TXT`
  (the UNB page no longer serves the files directly; mirrors verified by sha256
  via `portfolio_core.io.fetch`)
- **License/terms:** Research benchmark (UNB CIC); cite the NSL-KDD paper
  (Bahrololum et al., 2009) in derived work.
- **Used by:** Project 03 (real-data transfer probe — network-flow records
  behind the same `DatasetContract` as the synthetic telemetry default)
- **Size:** 125,973 train / 22,544 test records, 43 columns (41 mapped features;
  categorical factorized with the caveat documented in the project DESIGN.md).

## Snapshot policy

| Field | Value |
|---|---|
| Snapshot date | 2026-10-13 |
| Format | CSV (`.TXT`), headerless, comma-separated |
| Checksums | pinned in `projects/03-anomaly-detection/data/raw/checksums.json` |

## Access

Via Project 03's prepare stage / `anomaly_detection.nsl` module (fetch +
checksum + schema mapping). The transfer probe reports ROC-AUC 0.8817 /
PR-AUC 0.8916 at 56.9% test prevalence, with the caveats documented in the
project (labeled transfer probe, unseen attack categories, flow-vs-telemetry
semantics, factorized categoricals).
