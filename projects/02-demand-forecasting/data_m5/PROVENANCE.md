# M5 subset (wave 24)

Source: **M5 Forecasting Competition** (Walmart, US) accuracy track, loaded
via the Nixtla `datasetsforecast` package from its public mirror
(`github.com/Nixtla/m5-forecasts`, no Kaggle credentials required) and
subset locally. Original data: 30,490 store-item daily unit-sales series,
2011-01-29 → 2016-06-19, with exogenous sell_price, SNAP flags, and event
name/type calendars (the M5 competition terms permit research use with
attribution; the canonical citation is the Makridakis et al. M5 competition
companion, IJF 2022).

Subset rule (deterministic, documented in `src/demand_forecasting/m5_data.py`):

1. rank stores by total units sold → keep the top 3 (`CA_3`, `CA_1`, `TX_2`);
2. within those stores, rank items by total units sold → keep the top 200
   (`HOBBIES`, `HOUSEHOLD`, `FOODS` depts all represented by volume);
3. result: **600 daily series, 1,105,594 rows**, mean zero-day share 0.162
   (dense demand — the regime where ML forecasting demonstrably beats
   seasonal baselines, unlike the sparse UCI Online Retail II track).

Files (committed, offline-loadable):

| file | content |
|---|---|
| `subset_Y.parquet` | long frame `unique_id, ds, y` |
| `subset_X.parquet` | exogenous `unique_id, ds, sell_price, snap_*, event_*` |
| `subset_S.parquet` | static `unique_id, item_id, dept_id, cat_id, store_id, state_id` |

Package pins at subset time: datasetsforecast 1.0.2, statsforecast 2.1.1,
mlforecast 1.1.0.

# M5 full panel (m5_full wave, Phase 0)

Source: same Nixtla mirror — `M5.load('<data_dir>')` from `datasetsforecast`
downloads `https://github.com/Nixtla/m5-forecasts/raw/main/datasets/m5.zip`
(Kaggle-redistributable mirror of the M5 accuracy-track CSVs, no credentials)
and writes a parquet cache. Retrieved **2026-11-02** (UTC) into `raw/`:

| file | content | sha256 |
|---|---|---|
| `raw/m5/datasets/m5.zip` | the downloaded archive (calendar, sales train/test evaluation+validation, sell_prices, official weights CSVs) | `cc704ba15d6802f8262e6ec7d4c6041e4ad6366a94365e8c84f721e450eed774` |
| `raw/.cache/m5/m5/Y_df.parquet` | long frame `unique_id, ds, y` | `bdd4c6fd4c6544188212e805fb5708b1431049a6dae72d11e51842de8310d875` |
| `raw/.cache/m5/m5/X_df.parquet` | exog `unique_id, ds, event_name_1/2, event_type_1/2, snap_CA/TX/WI, sell_price` | `b2a4400de3dc8e267edaa3936224a0a51b544cef654bd2e535f199b2913ab0af` |
| `raw/.cache/m5/m5/S_df.parquet` | static `unique_id, item_id, dept_id, cat_id, store_id, state_id` | `856d9780b1ec0f1bab129d7aa8390a86f9c14ad177665074deb3368427c7df97` |

Verified panel facts (2026-11-02, `datasetsforecast` 1.0.2):

- **30,490 series** (3,049 items × 10 stores), **47,649,940 rows** in Y/X
  (leading zero-run days trimmed per series by the loader);
- every series is **contiguous from its first sale to 2016-06-19** — no holes
  (the loader inner-joins the weekly sell_price table; price coverage and the
  first-sale trim coincide exactly), so the panel is a full rectangle per
  series; first-sale dates span 2011-01-29 → 2016-02-17;
- **1,969 days, 2011-01-29 → 2016-06-19** — the panel INCLUDES the
  competition evaluation window (d_1942–d_1969 = 2016-05-23 → 2016-06-19);
  total units 68,156,320; zero-day share 0.595 (the full assortment is much
  sparser than the dense subset's 0.162);
- X carries the event name/type calendars (no-event = the literal string
  `"nan"`, same convention as the subset parquet), the three state SNAP
  flags, and per-(series, day) sell_price with **zero nulls**;
- hierarchy cardinalities from S_df: 3 states, 10 stores, 3 categories,
  7 departments, 3,049 items → the 12 official levels aggregate to
  1 + 3 + 10 + 3 + 7 + 9 + 21 + 30 + 70 + 3,049 + 9,147 + 30,490 = **42,840
  series**; level weights for the official WRMSSE are computable offline as
  last-28-day revenue (units × sell_price) per node.

The extracted CSVs are regenerable from `m5.zip` and were deleted after
caching; `load_m5_full` (src/demand_forecasting/m5_full.py) sha-pins the zip
and the three cache parquets before reading.
