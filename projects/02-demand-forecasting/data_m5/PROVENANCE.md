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
