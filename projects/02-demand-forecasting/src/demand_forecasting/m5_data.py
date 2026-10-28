"""M5 subset loader and split utilities (wave 24).

The M5 track (m5_track.py, protocol ``m5_direct_v1``) runs on the committed
Walmart M5 subset under ``data_m5/`` — 600 daily store-item series
(top-3 stores CA_3/CA_1/TX_2 x top-200 volume items), 2011-01-29..2016-06-19,
1,105,594 rows — built offline from the Nixtla ``datasetsforecast`` mirror and
frozen with sha256 pins (see ``data_m5/PROVENANCE.md``). Everything here is
offline: loading verifies the pins before reading and fails loudly on drift,
exactly like the UCI track's snapshot pin (uci.py).

Conventions:
- the modelling layer is pandas: statsforecast 2.1.1 requires a valid polars
  offset string for polars frames (``freq='D'`` is rejected), pandas is the
  verified path (see the API notes in the wave-24 plan);
- ``unique_id`` is cast from polars Categorical to plain str on load;
- exogenous variables are calendar/price data known in advance (sell_price is
  forward-filled per series into the future window — documented), never actuals,
  so future frames are leakage-free by construction.
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from portfolio_core.io import sha256_of
from portfolio_core.logging import get_logger

logger = get_logger(__name__)

#: sha256 pins of the committed subset (computed at subset time, wave 24).
M5_CHECKSUMS = {
    "subset_Y.parquet": "52dfc7d31d830d37f7b8b7b3ea886e353699816ab3bc56702c5e1c77b3a2a2b7",
    "subset_X.parquet": "6bac678a3dd6aadc161422c90bc072464039e0a7eee0dd89ebd084a61124ff06",
    "subset_S.parquet": "01a1593870f1f89531738cecce793e4b7d6804abdaa25a134e624b7a0884cf25",
}

#: Expected long-frame schema, enforced at load (the audit anchor).
_Y_COLUMNS = ("unique_id", "ds", "y")
_X_COLUMNS = (
    "unique_id",
    "ds",
    "event_name_1",
    "event_type_1",
    "event_name_2",
    "event_type_2",
    "snap_CA",
    "snap_TX",
    "snap_WI",
    "sell_price",
)
_S_COLUMNS = ("unique_id", "item_id", "dept_id", "cat_id", "store_id", "state_id")
#: Exogenous variables the lgbm candidate consumes (post encoding).
EXOG_FEATURES = (
    "sell_price",
    "snap",
    "event_name_1_code",
    "event_type_1_code",
    "event_name_2_code",
    "event_type_2_code",
)
#: SNAP flag per M5 state (the subset covers CA_3/CA_1/TX_2 -> CA and TX).
_STATE_SNAP = {"CA": "snap_CA", "TX": "snap_TX", "WI": "snap_WI"}


def verify_m5_checksums(data_dir: Path) -> dict[str, str]:
    """Check every committed parquet against its pin; returns {name: sha256}.

    Missing files and pin mismatches raise ValueError (the track must never
    silently evaluate a drifted dataset).
    """
    out: dict[str, str] = {}
    for name, expected in M5_CHECKSUMS.items():
        path = Path(data_dir) / name
        if not path.exists():
            raise ValueError(f"missing M5 subset file: {path}")
        actual = sha256_of(path)
        if actual != expected:
            raise ValueError(
                f"M5 subset checksum changed for {name}: {actual}. "
                "The committed subset no longer matches the wave-24 pin."
            )
        out[name] = actual
    return out


def load_m5_subset(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load (Y, X, S) from the committed, checksum-pinned subset parquets.

    ``Y``: ``unique_id, ds, y`` (daily units, f32); ``X``: exogenous
    ``sell_price, snap_*, event_*`` per (series, day); ``S``: static
    ``item/dept/cat/store/state``. ``unique_id`` is cast to str and ``ds`` to
    pandas datetime; Y/X are sorted by (unique_id, ds). The expected columns
    and the series/day counts are asserted so a corrupted subset fails here,
    not mid-backtest.
    """
    data_dir = Path(data_dir)
    verify_m5_checksums(data_dir)
    y_pl = pl.read_parquet(data_dir / "subset_Y.parquet")
    x_pl = pl.read_parquet(data_dir / "subset_X.parquet")
    s_pl = pl.read_parquet(data_dir / "subset_S.parquet")
    if tuple(y_pl.columns) != _Y_COLUMNS:
        raise ValueError(f"subset_Y schema drifted: {y_pl.columns}")
    if tuple(x_pl.columns) != _X_COLUMNS:
        raise ValueError(f"subset_X schema drifted: {x_pl.columns}")
    if tuple(s_pl.columns) != _S_COLUMNS:
        raise ValueError(f"subset_S schema drifted: {s_pl.columns}")

    y = y_pl.with_columns(pl.col("unique_id").cast(pl.String)).to_pandas(
        use_pyarrow_extension_array=False
    )
    x = x_pl.with_columns(pl.col("unique_id").cast(pl.String)).to_pandas(
        use_pyarrow_extension_array=False
    )
    s = s_pl.with_columns(pl.col("unique_id").cast(pl.String)).to_pandas(
        use_pyarrow_extension_array=False
    )
    for frame in (y, x):
        frame["ds"] = pd.to_datetime(frame["ds"])
        frame.sort_values(["unique_id", "ds"], inplace=True, ignore_index=True)

    n_series = s["unique_id"].nunique()
    n_days = y["ds"].nunique()
    if y["unique_id"].nunique() != n_series or x["unique_id"].nunique() != n_series:
        raise ValueError("Y/X/S disagree on the series set")
    # M5 series start at their first observed sale (items are introduced over
    # the panel) but ALL run to the panel end; every series needs enough real
    # history for the 28-day-horizon lags (28 + horizon + slack).
    per_series = y.groupby("unique_id")["ds"].agg(["min", "max", "count"])
    if not (per_series["max"] == y["ds"].max()).all():
        raise ValueError("every series must run to the panel end date")
    if pd.Timestamp(per_series["min"].min()) > y["ds"].max() - pd.to_timedelta(120, unit="D"):
        raise ValueError("series with under ~4 months of history would break the lags")
    logger.info(
        "m5 subset: %d series, %d days (%s..%s), %d rows, first-sale span %s..%s",
        n_series,
        n_days,
        y["ds"].min().date(),
        y["ds"].max().date(),
        len(y),
        per_series["min"].min().date(),
        per_series["min"].max().date(),
    )
    return y, x, s


def encode_events(x: pd.DataFrame, state_col: pd.Series | None = None) -> pd.DataFrame:
    """Encode the exogenous block as model-ready numeric columns.

    - ``snap`` — the series' own state SNAP flag (CA_3/CA_1 -> snap_CA,
      TX_2 -> snap_TX; joined from S via ``state_col``, aligned on row order).
    - ``event_name_1/2_code``, ``event_type_1/2_code`` — integer category
      codes over the full frame, deterministic (sorted-category ordering), so
      LightGBM sees numeric columns. The no-event marker is its own category
      (nulls filled with ``"<none>"``); WHICH code that is depends on how the
      parquet represented nulls (real NaN sorts ``"<none>"`` first -> code 1,
      the string ``"nan"`` sorts last) — callers needing the event-day mask
      must resolve it from the mode, never a hardcoded code (see
      ``m5_demo_payload._event_mask``).

    Row order and count are preserved; the result carries
    ``unique_id, ds`` + :data:`EXOG_FEATURES`.
    """
    out = pd.DataFrame({"unique_id": x["unique_id"], "ds": x["ds"]})
    if state_col is None:
        snap = np.zeros(len(x), dtype=float)
    else:
        flag_cols = list(_STATE_SNAP.values())
        flags = x[flag_cols].to_numpy(dtype=float)
        state_arr = state_col.to_numpy()
        snap = np.zeros(len(x), dtype=float)
        for pos, state in enumerate(_STATE_SNAP):
            snap = np.where(state_arr == state, flags[:, pos], snap)
    out["snap"] = snap
    out["sell_price"] = x["sell_price"].to_numpy(dtype=float)
    for raw in ("event_name_1", "event_type_1", "event_name_2", "event_type_2"):
        filled = x[raw].astype("string").fillna("<none>")
        cat = pd.Categorical(filled, categories=sorted(filled.unique()))
        # +1 so pandas-missing codes (-1) would land at 0; every real row is
        # covered by the categories above. The no-event code is position-
        # dependent (see the docstring) — never hardcode it downstream.
        out[f"{raw}_code"] = (cat.codes + 1).astype(float)
    return out


def split_exogenous(
    x_enc: pd.DataFrame, series_ids: list[str], origin_date: pd.Timestamp, horizon: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(history, future) exogenous frames for one origin, aligned for mlforecast.

    ``history`` — the encoded exog rows with ``ds <= origin_date`` (mlforecast
    reads exog from the training frame). ``future`` — exactly ``horizon`` rows
    per series for the window ``origin_date + 1 .. origin_date + horizon`` with
    ``sell_price`` forward-filled per series from its last observed price
    (documented: M5 prices are set in advance; a missing future price carries
    the last known one) and ``snap``/event codes taken from the calendar block
    of X itself (known-in-advance regressors, never actuals). Both frames are
    sorted by (unique_id, ds) in ``series_ids`` order.
    """
    hist = x_enc[x_enc["ds"] <= origin_date]
    window_start = origin_date + pd.to_timedelta(1, unit="D")
    window_end = origin_date + pd.to_timedelta(horizon, unit="D")
    future = x_enc[(x_enc["ds"] >= window_start) & (x_enc["ds"] <= window_end)].copy()
    # every (series, future day) must exist in X (the calendar is complete);
    # sell_price ffills per series, event/snap codes are calendar-known
    last_price = (
        hist.sort_values("ds").groupby("unique_id")["sell_price"].last().reindex(series_ids)
    )
    future["sell_price"] = future["unique_id"].map(last_price).to_numpy(dtype=float)
    expected = len(series_ids) * horizon
    if len(future) != expected:
        raise ValueError(f"future exog has {len(future)} rows, expected {expected}")
    if future["sell_price"].isna().any():
        raise ValueError("future sell_price could not be forward-filled for every series")
    order = {sid: i for i, sid in enumerate(series_ids)}
    future["_o"] = future["unique_id"].map(order)
    future = future.sort_values(["_o", "ds"], ignore_index=True).drop(columns="_o")
    return hist, future


def rolling_origins(
    dates: np.ndarray,
    n_origins: int,
    horizon: int,
    min_train: int,
    spacing_days: int = 7,
) -> list[int]:
    """Origin indices (into the sorted ``dates`` array) for the backtest.

    Origin *o* trains on days ``0..o`` (so ``o + 1 >= min_train``) and scores
    the ``horizon`` days ``o+1..o+horizon`` (so ``o <= n_dates - horizon - 1``).
    Origins are ``spacing_days`` apart, and the LAST ``n_origins`` eligible
    origins are kept (the backtest window is anchored at the end of the panel,
    the M5 evaluation convention). Pure and deterministic; unit-tested.
    """
    n_dates = len(dates)
    first = min_train - 1
    last = n_dates - horizon - 1
    if last < first:
        raise ValueError(
            f"panel too short: {n_dates} dates, need >= {first + horizon + 1} "
            f"(min_train={min_train}, horizon={horizon})"
        )
    eligible = list(range(first, last + 1, spacing_days))
    if len(eligible) > n_origins:
        # anchor at the panel end: drop the oldest origins (cadence preserved)
        eligible = eligible[-n_origins:]
    return eligible


def m5_dataset_metadata(data_dir: Path, y: pd.DataFrame, s: pd.DataFrame) -> dict[str, Any]:
    """Machine-readable block for evaluation_metadata.json (audit anchor)."""
    zero_share = float((y["y"] == 0).mean())
    return {
        "dataset": "M5 Forecasting Competition (Walmart) — accuracy track subset",
        "subset_rule": "top-3 stores by total units (CA_3, CA_1, TX_2) x top-200 items "
        "by total units within those stores; deterministic ranking, see "
        "data_m5/PROVENANCE.md",
        "provenance_ref": str(Path(data_dir) / "PROVENANCE.md"),
        "checksums_sha256": dict(M5_CHECKSUMS),
        "observed_panel": {
            "date_start": str(y["ds"].min().date()),
            "date_end": str(y["ds"].max().date()),
            "n_days": int(y["ds"].nunique()),
            "n_rows": len(y),
            "n_series": int(s["unique_id"].nunique()),
            "zero_share": zero_share,
            "stores": sorted(s["store_id"].unique().tolist()),
        },
        "citation": "Makridakis et al., M5 competition companion, International Journal "
        "of Forecasting (2022); research use with attribution per competition terms",
    }
