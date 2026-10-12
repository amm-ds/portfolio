#!/usr/bin/env python3
"""Fetch NOAA GHCN-Daily per-station file (Central Park) with checksum pinning."""

import argparse
import json
from pathlib import Path

from portfolio_core.io import fetch, sha256_of
from portfolio_core.logging import get_logger, setup_logging

logger = get_logger(__name__)

URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/USW00094728.csv.gz"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--checksums", type=Path, default=None)
    args = ap.parse_args()
    setup_logging("INFO")

    pins: dict[str, str] = {}
    if args.checksums and args.checksums.exists():
        pins = json.loads(args.checksums.read_text())

    dest = args.dest / "USW00094728.csv.gz"
    path = fetch(URL, dest, pins.get("USW00094728.csv.gz"))
    logger.info("fetched %s sha256=%s", path, sha256_of(path))


if __name__ == "__main__":
    main()
