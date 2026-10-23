"""Data preparation: synthetic or UCI real panel, contract + DQ gates, parquet.

Two tracks, selected by ``ForecastConfig.data_source``:

- ``synthetic`` (default): the platform's seeded ``retail_hierarchy``
  generator — offline/CI-safe, byte-identical everywhere.
- ``uci``: UCI Online Retail II (see ``uci.py``) — real invoice-line data,
  checksum-pinned download, network required on first fetch only.

Both produce the same panel schema, so every downstream module is unchanged.
"""

from datetime import date
from pathlib import Path
from typing import cast

import polars as pl
from portfolio_core.dq import DQReport
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract
from portfolio_core.synthetic import checksum_of_frame, retail_hierarchy

from demand_forecasting.config import DemandSettings, ForecastConfig

logger = get_logger(__name__)

PANEL_SCHEMA = {"date": pl.Date, "store": pl.String, "product": pl.String, "units": pl.Int64}

# per-track dataset identity
TRACKS: dict[str, dict[str, str]] = {
    "synthetic": {
        "name": "retail-hierarchy-synthetic",
        "version": "1.0.0",
        "source": "synthetic://retail_hierarchy",
        "license": "CC0-1.0",
        "snapshot": "2023-12-31",
    },
    "uci": {
        "name": "uci-online-retail-ii",
        "version": "1.0.0",
        "source": "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip",
        "license": "free-for-research (Chen et al. 2012)",
        "snapshot": "2026-10-12",
    },
}


def build_panel(settings: DemandSettings, config: ForecastConfig) -> pl.DataFrame:
    """Build the daily store-product panel for the configured track."""
    if config.data_source == "uci":
        from demand_forecasting.uci import build_uci_panel

        return build_uci_panel(settings, config)
    logger.info(
        "generating synthetic hierarchy: %d days, %d stores, %d products (seed=%d)",
        config.n_days,
        config.n_stores,
        config.n_products,
        settings.seed,
    )
    df = retail_hierarchy(
        seed=settings.seed,
        n_days=config.n_days,
        n_stores=config.n_stores,
        n_products=config.n_products,
    )
    return df.with_columns(pl.col("date").str.to_date("%Y-%m-%d"))


def validate_panel(df: pl.DataFrame, settings: DemandSettings, config: ForecastConfig) -> DQReport:
    """Run the platform DQ gates; raises :class:`DQGateError` if any fails."""
    track = TRACKS[config.data_source]
    report = DQReport(dataset=track["name"], n_rows=df.height)
    for col in ("date", "store", "product", "units"):
        null_rate = cast(float, df[col].is_null().mean())
        report.check_null_rate(col, null_rate, max_null_rate=0.0)
    units_min = cast(int, df["units"].min())
    units_max = cast(int, df["units"].max())
    report.check_range(
        "units",
        float(units_min),
        float(units_max),
        lo=0.0,
        hi=1_000_000.0,
    )
    newest = cast(date, df["date"].max())
    freshness_floor = (
        config.uci_min_newest_date if config.data_source == "uci" else settings.min_newest_date
    )
    report.check_freshness(
        newest_date=newest.strftime("%Y-%m-%d"),
        min_date=freshness_floor,
    )
    report.raise_if_failed()
    return report


def dataset_contract(df: pl.DataFrame, config: ForecastConfig) -> DatasetContract:
    """Versioned identity card for the prepared panel (checksum-pinned)."""
    track = TRACKS[config.data_source]
    return DatasetContract(
        name=track["name"],
        version=track["version"],
        source=track["source"],
        license=track["license"],
        snapshot_date=date.fromisoformat(track["snapshot"]),
        checksum_sha256=checksum_of_frame(df),
        n_rows=df.height,
    )


def prepare(settings: DemandSettings, config: ForecastConfig) -> Path:
    """Build, validate and persist the panel; returns the parquet path."""
    df = build_panel(settings, config)
    report = validate_panel(df, settings, config)
    logger.info("DQ gates passed (%d checks)\n%s", len(report.checks), report.to_markdown())

    out = settings.data_dir / "panel.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    logger.info("wrote %s (%d rows)", out, df.height)

    contract = dataset_contract(df, config)
    contract_path = settings.data_dir / "dataset.json"
    contract_path.write_text(contract.model_dump_json(indent=2))
    logger.info(
        "dataset contract -> %s (sha256=%s...)", contract_path, contract.checksum_sha256[:12]
    )
    if config.data_source == "uci":
        from demand_forecasting.uci import write_dataset_metadata

        write_dataset_metadata(settings, config, df)
    return out
