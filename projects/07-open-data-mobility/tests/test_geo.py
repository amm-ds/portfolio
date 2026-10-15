"""Geo figures (wave 13): choropleth builder on a tiny synthetic zone set."""

import geopandas as gpd  # type: ignore[import-untyped]
import polars as pl
from mobility.geo import _choropleth, fig_zone_demand_map, fig_zone_residual_map
from shapely.geometry import box


def _tiny_zones() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "LocationID": [1, 2],
            "zone": ["A", "B"],
            "borough": ["X", "Y"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        },
        crs=4326,
    )


def test_choropleth_maps_values_to_zones(monkeypatch) -> None:
    import mobility.geo as geo

    monkeypatch.setattr(geo, "_zones_geo", lambda *a, **k: _tiny_zones())
    fig = _choropleth(_tiny_zones(), {1: 10.0, 2: 20.0}, "t", "Teal", "v")
    assert list(fig.data[0].z) == [10.0, 20.0]
    assert list(fig.data[0].locations) == [1, 2]


def test_demand_and_residual_maps_takeaways(monkeypatch) -> None:
    import mobility.geo as geo

    monkeypatch.setattr(geo, "_zones_geo", lambda *a, **k: _tiny_zones())
    demand = pl.DataFrame({"zone_id": [1, 1, 2], "pickup_count": [4, 8, 10]})
    fig = fig_zone_demand_map(demand)
    assert list(fig.data[0].z) == [6.0, 10.0]  # mean pickups per zone-hour

    preds = pl.DataFrame(
        {"zone_id": [1, 1, 2], "y_true": [10, 10, 5], "y_gbm_tuned": [11.0, 9.0, 4.0]}
    )
    fig = fig_zone_residual_map(preds)
    # zone 1 MAPE = mean(10%, 10%) = 10% -> 10.0; zone 2 = 20% -> 20.0
    assert list(fig.data[0].z) == [10.0, 20.0]
