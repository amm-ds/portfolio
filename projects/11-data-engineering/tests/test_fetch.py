"""Fetch pins: sha256-pinned downloads, params/config consistency, registry link.

Offline by design: the real snapshot is fetched once by ``fetch-data``; these
tests exercise the pin machinery against local files served over ``file://``
(the scheme ``portfolio_core.io.fetch`` allows for exactly this) and check the
committed pins against the data-registry entry for the same snapshot family.
"""

import re
from pathlib import Path

import pytest
import yaml
from data_engineering.config import DEConfig
from data_engineering.fetch import (
    TLC_LICENSE,
    TRIPS_RAW_NAME,
    ZONES_RAW_NAME,
    load_real_bundle,
)
from portfolio_core.io import fetch, sha256_of

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_DVC = REPO_ROOT / "registry" / "nyc-tlc-yellow-2024-01.dvc"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Byte size recorded in registry/nyc-tlc-yellow-2024-01.dvc (etag-pinned upstream).
_REGISTRY_SIZE = 49_961_641


def _pin_case(tmp_path: Path) -> tuple[Path, str]:
    payload = tmp_path / "snapshot.bin"
    payload.write_bytes(b"synthetic snapshot bytes v1")
    return payload, sha256_of(payload)


def test_fetch_verifies_sha256_and_is_idempotent(tmp_path: Path) -> None:
    """file:// fetch with the right pin succeeds; a second run skips re-download."""
    payload, checksum = _pin_case(tmp_path)
    dest = tmp_path / "downloads" / "snapshot.bin"
    first = fetch(payload.as_uri(), dest, checksum)
    assert first == dest
    mtime = dest.stat().st_mtime_ns
    second = fetch(payload.as_uri(), dest, checksum)
    assert second.stat().st_mtime_ns == mtime, "pinned re-fetch must not rewrite the file"


def test_fetch_rejects_bad_pin(tmp_path: Path) -> None:
    """A wrong pin fails loudly and leaves no partial file behind."""
    payload, _ = _pin_case(tmp_path)
    dest = tmp_path / "downloads" / "snapshot.bin"
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch(payload.as_uri(), dest, "0" * 64)
    assert not dest.exists()


def test_fetch_rejects_bad_scheme(tmp_path: Path) -> None:
    payload, checksum = _pin_case(tmp_path)
    with pytest.raises(ValueError, match="scheme"):
        fetch(f"ftp://example.com/{payload.name}", tmp_path / "x.bin", checksum)


def test_pins_are_well_formed_and_match_params(tmp_path: Path) -> None:
    """params.yaml pins, config defaults and fetch constants agree."""
    cfg = DEConfig(data_dir=tmp_path, reports_dir=tmp_path / "r")
    params = yaml.safe_load((Path(__file__).resolve().parents[1] / "params.yaml").read_text())

    assert _SHA256_RE.match(cfg.trips_sha256)
    assert _SHA256_RE.match(cfg.zones_sha256)
    assert params["trips_sha256"] == cfg.trips_sha256
    assert params["zones_sha256"] == cfg.zones_sha256
    assert params["trips_url"] == cfg.trips_url
    assert params["zones_url"] == cfg.zones_url
    assert TRIPS_RAW_NAME in cfg.trips_url and ZONES_RAW_NAME in cfg.zones_url
    assert "TLC" in TLC_LICENSE


@pytest.mark.skipif(not REGISTRY_DVC.exists(), reason="registry dvc entry not present")
def test_trips_pin_matches_registry_snapshot() -> None:
    """The real-track pin is the same snapshot the data registry pins for 07."""
    text = REGISTRY_DVC.read_text()
    assert f"size: {_REGISTRY_SIZE}" in text
    cfg = DEConfig()
    assert cfg.trips_url in text, "trips URL must be the registry-pinned URL"
    # The pinned sha256 was computed from the registry-identical download
    # (same size/etag); the fetch gate re-verifies it on every real-track run.
    assert cfg.trips_sha256 == "c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510"


def test_real_bundle_fails_loudly_without_data(tmp_path: Path) -> None:
    """Loading the real track without fetch-data fails with a clear message."""
    cfg = DEConfig(data_dir=tmp_path, reports_dir=tmp_path / "r")
    with pytest.raises(FileNotFoundError):
        load_real_bundle(cfg)
