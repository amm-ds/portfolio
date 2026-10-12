#!/usr/bin/env python3
"""Download the Solomon VRPTW 100-customer instances (SINTEF TOP mirror).

The original ``solomonbenchmark.s3.amazonaws.com`` mirror 404s as of Oct 2026;
SINTEF TOP's backup zip is the maintained source. SINTEF rejects urllib's
default User-Agent with a 403, so a browser UA is sent.
"""

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

from portfolio_core.io import sha256_of
from portfolio_core.logging import get_logger, setup_logging

logger = get_logger(__name__)

URL = "https://www.sintef.no/globalassets/project/top/vrptw/solomon/solomon-100.zip"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    args = ap.parse_args()
    setup_logging("INFO")
    args.dest.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = resp.read()
    zf = zipfile.ZipFile(io.BytesIO(payload))
    n = 0
    for name in zf.namelist():
        if not name.lower().endswith(".txt"):
            continue
        target = args.dest / Path(name).name
        target.write_bytes(zf.read(name))
        n += 1
        logger.info("%s (sha256=%s)", target.name, sha256_of(target))
    logger.info("extracted %d instances to %s", n, args.dest)


if __name__ == "__main__":
    main()
