"""Geo views (wave 13): TLC zone choropleths for demand and model residuals.

Boundaries: the official TLC ``taxi_zones.zip`` shapefile (checksum-pinned in
``data/raw/checksums.json``; source noted in the data-registry card). Read via
geopandas/pyogrio, reprojected to WGS84 for plotting, joined to the curated
zone-hour grain on ``LocationID``.

Two figures:
- ``zone_demand_map`` — mean pickups per zone-hour (the demand geography);
- ``zone_residual_map`` — per-zone MAPE of the served GBM (where the model
  struggles geographically).
"""

import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path

import geopandas as gpd  # type: ignore[import-untyped]
import plotly.graph_objects as go
import polars as pl
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme

from mobility.config import get_config

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _zones_geo(cfg_key: str = "") -> gpd.GeoDataFrame:
    """Zone boundaries (WGS84), cached per process."""
    cfg = get_config()
    zf = cfg.raw_dir / "taxi_zones.zip"
    if not zf.exists():
        raise FileNotFoundError(f"missing {zf} — run `mobility download`")
    tmp = Path(tempfile.mkdtemp(prefix="taxi_zones_"))
    with zipfile.ZipFile(zf) as z:
        z.extractall(tmp)
    gdf = gpd.read_file(tmp / "taxi_zones" / "taxi_zones.shp", engine="pyogrio")
    return gdf.to_crs(4326)[["LocationID", "zone", "borough", "geometry"]]


def _choropleth(
    gdf: gpd.GeoDataFrame,
    values: dict[int, float],
    title: str,
    colorscale: str,
    colorbar_title: str,
) -> go.Figure:
    geojson = gdf.__geo_interface__
    fig = go.Figure(
        go.Choroplethmap(
            geojson=geojson,
            locations=gdf["LocationID"].tolist(),
            z=[values.get(int(zid), 0.0) for zid in gdf["LocationID"].tolist()],
            featureidkey="properties.LocationID",
            colorscale=colorscale,
            marker_opacity=0.75,
            marker_line_width=0.5,
            marker_line_color="#0f172a",
            colorbar={"title": colorbar_title},
        )
    )
    fig.update_layout(
        title=title,
        map_style="carto-darkmatter",
        map_center={"lat": 40.72, "lon": -73.95},
        map_zoom=9.5,
    )
    return apply_theme(fig, height=640)


def fig_zone_demand_map(demand: pl.DataFrame) -> go.Figure:
    """(a) Mean pickups per zone-hour across the curated year (demand geography)."""
    means = {
        int(r["zone_id"]): float(r["m"])
        for r in demand.group_by("zone_id")
        .agg(pl.col("pickup_count").mean().alias("m"))
        .iter_rows(named=True)
    }
    top = max(means, key=lambda k: means[k])
    gdf = _zones_geo()
    fig = _choropleth(
        gdf,
        means,
        "Demand concentrates in Midtown and the airports",
        "Teal",
        "pickups/h",
    )
    return add_takeaway(
        fig,
        f"Demand concentrates in Midtown/Manhattan cores and JFK/EWR airports; "
        f"busiest zone averages {means[top]:.1f} pickups/hour.",
    )


def fig_zone_residual_map(preds: pl.DataFrame, col: str = "y_gbm_tuned") -> go.Figure:
    """(b) Per-zone MAPE of the served GBM — where the model struggles."""
    pred_col = col if col in preds.columns else "y_gbm"
    per_zone = (
        preds.filter(pl.col("y_true") > 0)
        .with_columns(ape=(pl.col(pred_col) - pl.col("y_true")).abs() / pl.col("y_true"))
        .group_by("zone_id")
        .agg(pl.col("ape").mean().alias("mape"))
    )
    mape = {int(r["zone_id"]): float(r["mape"]) * 100 for r in per_zone.iter_rows(named=True)}
    worst = max(mape, key=lambda k: mape[k])
    gdf = _zones_geo()
    fig = _choropleth(
        gdf,
        mape,
        "Where the model struggles — per-zone MAPE (%), served GBM",
        "Reds",
        "MAPE %",
    )
    return add_takeaway(
        fig,
        f"Highest relative error ({mape[worst]:.0f}% MAPE) sits in the thinnest-demand "
        "zones — relative error, not absolute: Manhattan dominates absolute MAE.",
    )
