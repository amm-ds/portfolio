"""Real track: fetch the registry-pinned NYC TLC slice and derive the prepared layout.

Downloads (checksum-pinned, idempotent — portfolio_core.io.fetch semantics):
the January 2024 yellow-taxi parquet (the exact snapshot family the data
registry pins for project 07 in ``registry/nyc-tlc-yellow-2024-01.dvc``: same
URL, byte size and source etag) plus the taxi-zone lookup CSV. ``fetch-data``
then projects the eight working columns out of the raw 20-column file and
materializes what the tasks read: ``trips.parquet``, ``trips.csv`` and the
31-way hive-partitioned per-day parquet directory. VendorID and payment_type
are cast to strings here, once, so the string-categorical aggregation task is
string-shaped on the real track exactly as on the synthetic one.
"""

import polars as pl
import pyarrow.parquet as pq
from portfolio_core.io import fetch, sha256_of
from portfolio_core.logging import get_logger

from data_engineering.config import DEConfig
from data_engineering.data import DataBundle
from data_engineering.synthetic import TRIP_COLUMNS, write_dataset_contract

logger = get_logger(__name__)

TRIPS_RAW_NAME = "yellow_tripdata_2024-01.parquet"
ZONES_RAW_NAME = "taxi_zone_lookup.csv"
TLC_LICENSE = "NYC TLC terms of use; free anonymous download, no account"


def fetch_data(cfg: DEConfig) -> DataBundle:
    """Download the pinned snapshot and write the prepared layout + contract."""
    raw = cfg.raw_path
    raw.mkdir(parents=True, exist_ok=True)

    trips_raw = fetch(cfg.trips_url, raw / TRIPS_RAW_NAME, cfg.trips_sha256)
    zones_raw = fetch(cfg.zones_url, raw / ZONES_RAW_NAME, cfg.zones_sha256)
    checksum = sha256_of(trips_raw)
    logger.info("raw trips sha256 ok: %s", checksum[:12])
    del zones_raw  # presence + checksum verified by fetch; the bundle re-checks

    trips = pl.read_parquet(trips_raw, columns=list(TRIP_COLUMNS)).with_columns(
        pl.col("VendorID").cast(pl.String),
        pl.col("payment_type").cast(pl.String),
    )
    n_rows = pq.read_metadata(trips_raw).num_rows

    prepared = cfg.prepared_path
    partitioned = prepared / "partitioned"
    partitioned.mkdir(parents=True, exist_ok=True)
    trips.write_parquet(prepared / "trips.parquet", compression="snappy")
    trips.write_csv(prepared / "trips.csv")
    day = trips["tpep_pickup_datetime"].dt.day()
    for d in sorted(day.unique().to_list()):
        part = partitioned / f"day={d:02d}"
        part.mkdir(parents=True, exist_ok=True)
        trips.filter(day == d).write_parquet(part / "part-0.parquet", compression="snappy")
    logger.info(
        "prepared layout written: %d rows, %d day partitions",
        n_rows,
        len(list(partitioned.glob("day=*"))),
    )

    write_dataset_contract(
        cfg.data_dir,
        source=cfg.trips_url,
        n_rows=n_rows,
        checksum=checksum,
        license_text=TLC_LICENSE,
    )
    return load_real_bundle(cfg)


def load_real_bundle(cfg: DEConfig) -> DataBundle:
    """Re-validate the pinned snapshot and return the bundle for the harness."""
    raw = cfg.raw_path
    trips_raw = raw / TRIPS_RAW_NAME
    bundle = DataBundle(
        data_dir=cfg.data_dir,
        n_rows=pq.read_metadata(trips_raw).num_rows,
        checksum_sha256=cfg.trips_sha256,
        source=cfg.trips_url,
        license=TLC_LICENSE,
        notes=(
            "Real track: NYC TLC yellow taxi January 2024, 8-column working projection "
            "(VendorID/payment_type as strings) of the registry-pinned snapshot "
            "(registry/nyc-tlc-yellow-2024-01.dvc)."
        ),
    )
    # The pin gate runs on every load: a republished upstream file fails here.
    actual = sha256_of(trips_raw)
    if actual != cfg.trips_sha256:
        raise ValueError(
            f"checksum mismatch for {trips_raw}: expected {cfg.trips_sha256}, got {actual}. "
            "The upstream snapshot changed — update params.yaml + the dataset card deliberately."
        )
    bundle.validate()
    return bundle
