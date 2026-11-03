# Walmart M5 (Nixtla mirror)

- **Canonical source:** https://www.kaggle.com/c/m5-forecasting-accuracy (competition
  page; data originally © Walmart, distributed for competition/research use)
- **Mirror used by this repo:** https://github.com/Nixtla/m5-forecasts/raw/main/datasets/m5.zip
  (via the `datasetsforecast` package's M5 loader)
- **License/terms:** Kaggle competition data — research and educational use;
  cite Makridakis, S. et al. (2022), "M5 accuracy competition: Results,
  findings, and conclusions", International Journal of Forecasting 38(4),
  1346–1364.
- **Used by:** Project 02 (canonical M5 track, full bottom-level panel)
- **Size:** 30,490 daily store-item series × 1,969 days (2011-01-29..2016-06-19,
  includes the 28-day competition evaluation window), with calendar, SNAP and
  sell-price exogenous and item/department/category/store/state statics.

## Snapshot policy

The mirror zip and its parquet cache are sha256-pinned in
`projects/02-demand-forecasting/data_m5/PROVENANCE.md` (four pins: zip +
Y/X/S parquet cache). Checksum verification on load is mandatory — the loader
refuses drift.

| Field | Value |
|---|---|
| Snapshot date | 2026-11-02 |
| Format | zip → parquet cache (`Y_df`, `X_df`, `S_df`) |

## Access

```bash
cd projects/02-demand-forecasting
uv run python -c "from datasetsforecast.m5 import M5; M5.load('data_m5/raw')"
```
