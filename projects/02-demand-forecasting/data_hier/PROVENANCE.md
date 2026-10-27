# Hierarchical benchmark datasets (wave 23)

Source: the Nixtla `datasetsforecast` package (`datasetsforecast.hierarchical`),
which hosts the hierarchical forecasting benchmark datasets of
Rangapuram et al. (ICML 2021), Olivares et al. (IJF 2023) and Kamarthi et al.
(PROFHIT, 2022) — see https://nixtlaverse.nixtla.io/datasetsforecast/hierarchical.html.

Groups used by this project:

| group | freq | nodes | span |
|---|---|---|---|
| TourismSmall | quarterly | 89 (56 bottom) | 1998Q1–2006Q4 |
| Labour | monthly | 57 (32 bottom) | 1978–2019 |

Downloaded once with `HierarchicalData.load("data_hier", group)` and committed
so CI/tests run offline. Raw downloads live under `hierarchical/`; the parquet
cache under `hierarchical/.cache/` is the load format.
Package pins at download time: datasetsforecast 1.0.2, statsforecast 2.1.1,
mlforecast 1.1.0, hierarchicalforecast 1.5.3.
