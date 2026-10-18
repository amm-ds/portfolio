"""Checksum-pinned fetching. Loud failures, resumable semantics (data policy)."""

import hashlib
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from portfolio_core.logging import get_logger

logger = get_logger(__name__)

_CHUNK = 1 << 20  # 1 MiB
# Registry downloads are https; tests fetch local snapshots via file://.
# Anything else (custom schemes) is refused loudly.
_ALLOWED_SCHEMES = ("https", "http", "file")


def _check_scheme(url: str) -> None:
    if urllib.parse.urlparse(url).scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(f"refusing to fetch {url!r}: scheme must be one of {_ALLOWED_SCHEMES}")


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: str | Path, expected_sha256: str | None = None) -> Path:
    """Download ``url`` to ``dest``; verify sha256 when pinned; fail loudly.

    Skips the download if the destination exists and matches the pinned
    checksum (idempotent, resumable pipelines).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if expected_sha256 and dest.exists() and sha256_of(dest) == expected_sha256.lower():
        logger.info("cached %s (sha256 ok)", dest)
        return dest
    logger.info("fetching %s -> %s", url, dest)
    _check_scheme(url)
    with urllib.request.urlopen(url, timeout=300) as resp, open(dest, "wb") as f:  # noqa: S310
        shutil.copyfileobj(resp, f, length=_CHUNK)
    if expected_sha256:
        actual = sha256_of(dest)
        if actual != expected_sha256.lower():
            dest.unlink(missing_ok=True)
            raise ValueError(
                f"checksum mismatch for {url}: expected {expected_sha256}, got {actual}. "
                "The upstream snapshot changed — update the dataset card deliberately."
            )
    return dest
