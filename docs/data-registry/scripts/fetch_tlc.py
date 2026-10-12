#!/usr/bin/env python3
"""Fetch NYC TLC monthly Parquet files (yellow taxi) with checksum pinning.

Checksums are looked up from data-registry/checksums/tlc.json when present;
files already matching their pinned checksum are skipped (idempotent).
"""

import argparse
import json
from pathlib import Path

from portfolio_core.io import fetch
from portfolio_core.logging import get_logger, setup_logging

logger = get_logger(__name__)

BASE = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+", required=True, help="YYYY-MM list")
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--checksums", type=Path, default=None)
    args = ap.parse_args()
    setup_logging("INFO")

    pins: dict[str, str] = {}
    if args.checksums and args.checksums.exists():
        pins = json.loads(args.checksums.read_text())

    for month in args.months:
        url = BASE.format(month=month)
        path = fetch(url, args.dest / f"yellow_tripdata_{month}.parquet", pins.get(month))
        logger.info("%s -> %s", month, path)


if __name__ == "__main__":
    main()
