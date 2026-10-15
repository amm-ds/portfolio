"""Checksum-pinned acquisition of TLC + NOAA + zone lookup raw files.

First run records each file's sha256 in ``data/raw/checksums.json``; later runs
pass the pin to ``portfolio_core.io.fetch`` so any upstream republication
fails loudly (data-registry snapshot policy). One ``DatasetContract`` JSON per
file lands in ``data/raw/contracts/``.
"""

import gzip
import json
from datetime import date
from pathlib import Path

import polars as pl
from portfolio_core.io import fetch, sha256_of
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract

from mobility.config import MobilityConfig, get_config

logger = get_logger(__name__)

TLC_LICENSE = "NYC TLC terms of use (free, anonymous download; see data-registry/nyc-tlc.md)"
NOAA_LICENSE = "Public domain (US Government work)"


def _load_pins(registry: Path) -> dict[str, str]:
    if registry.exists():
        pins: dict[str, str] = json.loads(registry.read_text())
        return pins
    return {}


def _record_pin(registry: Path, name: str, checksum: str) -> None:
    registry.parent.mkdir(parents=True, exist_ok=True)
    pins = _load_pins(registry)
    pins[name] = checksum
    registry.write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n")


def _write_contract(
    cfg: MobilityConfig,
    *,
    name: str,
    source: str,
    license_: str,
    path: Path,
    n_rows: int,
) -> DatasetContract:
    contract = DatasetContract(
        name=name,
        version="1.0.0",
        source=source,
        license=license_,
        snapshot_date=date.today(),
        checksum_sha256=sha256_of(path),
        n_rows=n_rows,
    )
    cfg.contract_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.contract_dir / f"{name}.json"
    out.write_text(contract.model_dump_json(indent=2) + "\n")
    return contract


def _parquet_rows(path: Path) -> int:
    return int(pl.scan_parquet(path).select(pl.len()).collect(engine="streaming").item())


def _csv_rows(path: Path) -> int:
    """Count data lines of a (possibly gzipped) CSV without pandas."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    with open(path, encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


def download_all(cfg: MobilityConfig | None = None) -> list[DatasetContract]:
    """Fetch every raw file (idempotent), pin checksums, write contracts."""
    cfg = cfg or get_config()
    cfg.tlc_raw_dir.mkdir(parents=True, exist_ok=True)
    pins = _load_pins(cfg.checksum_registry)
    contracts: list[DatasetContract] = []

    for month in cfg.months:
        url = cfg.tlc_base_url.format(month=month)
        name = f"yellow_tripdata_{month}"
        dest = cfg.tlc_raw_dir / f"{name}.parquet"
        fetch(url, dest, pins.get(dest.name))
        checksum = sha256_of(dest)
        if dest.name not in pins:
            _record_pin(cfg.checksum_registry, dest.name, checksum)
            logger.info("pinned %s sha256=%s", dest.name, checksum)
        else:
            logger.info("checksum verified %s", dest.name)
        contracts.append(
            _write_contract(
                cfg,
                name=name,
                source=url,
                license_=TLC_LICENSE,
                path=dest,
                n_rows=_parquet_rows(dest),
            )
        )

    green_dir = cfg.raw_dir / "green"
    green_dir.mkdir(parents=True, exist_ok=True)
    for month in cfg.green_months:
        url = cfg.tlc_green_base_url.format(month=month)
        name = f"green_tripdata_{month}"
        dest = green_dir / f"{name}.parquet"
        fetch(url, dest, pins.get(dest.name))
        checksum = sha256_of(dest)
        if dest.name not in pins:
            _record_pin(cfg.checksum_registry, dest.name, checksum)
            logger.info("pinned %s sha256=%s", dest.name, checksum)
        else:
            logger.info("checksum verified %s", dest.name)
        contracts.append(
            _write_contract(
                cfg,
                name=name,
                source=url,
                license_=TLC_LICENSE,
                path=dest,
                n_rows=_parquet_rows(dest),
            )
        )

    shapes_dest = cfg.raw_dir / "taxi_zones.zip"
    fetch(cfg.zone_shapes_url, shapes_dest, pins.get(shapes_dest.name))
    checksum = sha256_of(shapes_dest)
    if shapes_dest.name not in pins:
        _record_pin(cfg.checksum_registry, shapes_dest.name, checksum)
        logger.info("pinned %s sha256=%s", shapes_dest.name, checksum)
    else:
        logger.info("checksum verified %s", shapes_dest.name)
    import zipfile

    with zipfile.ZipFile(shapes_dest) as z:
        n_rows = len(z.namelist())
    contracts.append(
        _write_contract(
            cfg,
            name="taxi_zones",
            source=cfg.zone_shapes_url,
            license_=TLC_LICENSE,
            path=shapes_dest,
            n_rows=n_rows,
        )
    )

    for name, url, license_ in [
        ("taxi_zone_lookup", cfg.zone_lookup_url, TLC_LICENSE),
        ("noaa_usw00094728_ghcn_daily", cfg.noaa_url, NOAA_LICENSE),
    ]:
        suffix = ".csv" if name == "taxi_zone_lookup" else ".csv.gz"
        dest = cfg.raw_dir / f"{name}{suffix}"
        fetch(url, dest, pins.get(dest.name))
        checksum = sha256_of(dest)
        if dest.name not in pins:
            _record_pin(cfg.checksum_registry, dest.name, checksum)
            logger.info("pinned %s sha256=%s", dest.name, checksum)
        else:
            logger.info("checksum verified %s", dest.name)
        contracts.append(
            _write_contract(
                cfg,
                name=name,
                source=url,
                license_=license_,
                path=dest,
                n_rows=_csv_rows(dest),
            )
        )

    logger.info(
        "download complete: %d files, %d rows of trips across %d months",
        len(contracts),
        sum(c.n_rows for c in contracts if c.name.startswith("yellow")),
        len(cfg.months),
    )
    return contracts
