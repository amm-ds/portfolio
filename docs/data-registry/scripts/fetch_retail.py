#!/usr/bin/env python3
"""Fetch UCI Online Retail II (XLSX, ~45 MB) from the UCI archive."""

import argparse
from pathlib import Path

from portfolio_core.io import fetch
from portfolio_core.logging import get_logger, setup_logging

logger = get_logger(__name__)

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    args = ap.parse_args()
    setup_logging("INFO")
    path = fetch(URL, args.dest / "online_retail_ii.zip")
    logger.info("fetched %s (unzip before prepare)", path)


if __name__ == "__main__":
    main()
