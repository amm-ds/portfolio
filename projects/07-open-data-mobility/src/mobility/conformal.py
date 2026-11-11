"""Stratified split-conformal calibration for the one-sided p90 band.

External audit pass 4: the quantile band's measured weakness is conditional
coverage — 90.8% overall but 84.7% in sparse zones. Split-conformal is the
standard post-hoc fix: an additive offset per zone-density stratum, fit on a
calibration window, moves the band up where it under-covers and down where
it over-covers at the same nominal level.

Protocol (stated in the metrics block, no leakage hand-waving):
- calibration = the FIRST half of the committed test window; evaluation =
  the SECOND half. The second half never enters the offset fitting.
- strata = terciles of per-zone mean demand on the calibration half
  (train-side statistics; the test half cannot influence its own grouping).
- offset per stratum = the one-sided split-conformal order statistic at
  level 1-alpha (Lei et al. 2018): the ceil((n+1)*(1-alpha))-th smallest
  calibration score y - q90. Offsets may be negative — dense zones are
  over-covered and the band tightens there.

The guarantees are marginal per stratum (exact coverage would need the
exchangeability the strata approximately restore); the block reports the
measured before/after, not the theory.
"""

import math
from typing import Any, cast

import plotly.graph_objects as go
import polars as pl
from portfolio_core.plotting import add_takeaway, apply_theme

STRATA_NAMES = ("sparse", "mid", "dense")


def _zone_strata(calib: pl.DataFrame) -> dict[int, str]:
    """Zone -> density stratum: terciles of calibration-half mean demand."""
    means = calib.group_by("zone_id").agg(pl.col("y_true").mean().alias("m")).sort("m")
    rows = means["zone_id"].to_list()
    n = len(rows)
    return {z: STRATA_NAMES[min(2, (3 * i) // max(n, 1))] for i, z in enumerate(rows)}


def conformal_offset(scores: list[float], alpha: float) -> float:
    """One-sided split-conformal offset: ceil((n+1)*(1-alpha))-th order stat."""
    n = len(scores)
    if n == 0:
        return 0.0
    k = min(n, math.ceil((n + 1) * (1.0 - alpha)))
    return sorted(scores)[k - 1]


def evaluate_conformal(
    preds: pl.DataFrame,
    p90_col: str,
    point_col: str,
    alpha: float = 0.1,
    calib_frac: float = 0.5,
) -> dict[str, Any]:
    """Before/after coverage of the p90 band under stratum-conformal offsets.

    Returns the offsets, per-stratum and overall coverage before/after, and
    the mean band height above the point forecast (the width trade-off for a
    one-sided band).
    """
    ts_sorted = preds["ts"].unique().sort()
    split_ts = ts_sorted[int(ts_sorted.len() * calib_frac)]
    calib = preds.filter(pl.col("ts") < split_ts)
    eval_df = preds.filter(pl.col("ts") >= split_ts)

    strata_map = _zone_strata(calib)
    strata_col = pl.Series(
        "density_stratum", [strata_map.get(z, "mid") for z in eval_df["zone_id"].to_list()]
    )
    eval_df = eval_df.with_columns(strata_col)
    calib_strata = pl.Series(
        "density_stratum", [strata_map.get(z, "mid") for z in calib["zone_id"].to_list()]
    )
    calib = calib.with_columns(calib_strata)

    offsets: dict[str, float] = {}
    for stratum in STRATA_NAMES:
        sub = calib.filter(pl.col("density_stratum") == stratum)
        scores = (sub["y_true"] - sub[p90_col]).to_list()
        offsets[stratum] = conformal_offset(scores, alpha)

    adjusted = eval_df.with_columns(
        pl.col("zone_id")
        .map_elements(lambda z: offsets[strata_map.get(z, "mid")], return_dtype=pl.Float64)
        .alias("_offset")
    ).with_columns((pl.col(p90_col) + pl.col("_offset")).alias("q90_conformal"))

    def _coverage(df: pl.DataFrame, col: str) -> float:
        if df.height == 0:
            return float("nan")  # stratum absent in this window — plotted as a gap
        return cast(float, (df["y_true"] <= df[col]).mean())

    def _height(df: pl.DataFrame, col: str) -> float:
        return cast(float, (df[col] - df[point_col]).mean())

    def _per_stratum(df: pl.DataFrame, col: str) -> dict[str, float]:
        return {
            s: _coverage(df.filter(pl.col("density_stratum") == s), col) for s in STRATA_NAMES
        }

    return {
        "method": "one-sided split-conformal offsets per zone-density tercile; "
        "calibration = first half of the committed test window, evaluation = second half; "
        "offsets from calibration scores y - q90 (marginal per-stratum coverage)",
        "alpha": alpha,
        "calib_rows": calib.height,
        "eval_rows": eval_df.height,
        "offsets": offsets,
        "before": {
            "coverage_overall": _coverage(adjusted, p90_col),
            "coverage_by_stratum": _per_stratum(adjusted, p90_col),
            "mean_height": _height(adjusted, p90_col),
        },
        "after": {
            "coverage_overall": _coverage(adjusted, "q90_conformal"),
            "coverage_by_stratum": _per_stratum(adjusted, "q90_conformal"),
            "mean_height": _height(adjusted, "q90_conformal"),
        },
    }


def fig_conformal_coverage(block: dict[str, Any]) -> go.Figure:
    """Grouped bars: empirical p90 coverage per stratum, before vs after."""
    labels = [*STRATA_NAMES, "overall"]
    before = [block["before"]["coverage_by_stratum"][s] for s in STRATA_NAMES] + [
        block["before"]["coverage_overall"]
    ]
    after = [block["after"]["coverage_by_stratum"][s] for s in STRATA_NAMES] + [
        block["after"]["coverage_overall"]
    ]
    fig = go.Figure(
        [
            go.Bar(name="raw quantile band", x=labels, y=before, marker_color="#64748b"),
            go.Bar(
                name="stratum-conformal band",
                x=labels,
                y=after,
                marker_color="#2dd4bf",
                text=[f"{v:.1%}" if v == v else "n/a" for v in after],
                textposition="outside",
            ),
        ]
    )
    fig.add_hline(y=1.0 - block["alpha"], line_dash="dash", line_color="#fbbf24")
    fig.update_layout(
        barmode="group",
        title="p90 band coverage: raw quantile vs stratum-conformal",
        yaxis_title="empirical coverage (target 90%)",
    )
    def _pct(v: float) -> str:
        return f"{v:.1%}" if v == v else "n/a"

    sparse_gain = (
        block["after"]["coverage_by_stratum"]["sparse"]
        - block["before"]["coverage_by_stratum"]["sparse"]
    )
    add_takeaway(
        fig,
        f"sparse zones {_pct(block['before']['coverage_by_stratum']['sparse'])} -> "
        f"{_pct(block['after']['coverage_by_stratum']['sparse'])} "
        f"({sparse_gain:+.1%}); overall {_pct(block['before']['coverage_overall'])} -> "
        f"{_pct(block['after']['coverage_overall'])} on the held-out second half",
    )
    return apply_theme(fig)
