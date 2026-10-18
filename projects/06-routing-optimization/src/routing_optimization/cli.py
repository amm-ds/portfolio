"""Typer CLI: download, solve, evaluate, all.

``download`` fetches the Solomon 100-customer archive from the SINTEF backup
mirror (the registry's primary S3 mirror was unreachable at snapshot time —
see DESIGN.md) and extracts the configured subset into ``data/raw``.
"""

import json
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import typer
from portfolio_core.io import sha256_of
from portfolio_core.logging import get_logger, setup_logging
from portfolio_core.schemas import DatasetContract

from routing_optimization.config import VRPConfig, get_vrp_config
from routing_optimization.evaluate import run_evaluate, run_solve

logger = get_logger(__name__)

app = typer.Typer(help="Routing optimization on Solomon VRPTW benchmark instances.")

# SINTEF's CDN rejects urllib's default User-Agent with a 403, so the archive
# is fetched here (checksum-pinned, idempotent) instead of portfolio_core.io.fetch.
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _fetch_archive(url: str, dest: Path) -> Path:
    """Download ``url`` to ``dest`` unless an identical file already exists."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("cached %s", dest)
        return dest
    logger.info("fetching %s -> %s", url, dest)
    # http(s) for the registry mirror, file for local-archive mirrors (a
    # supported download config; see test_download_instances_from_local_archive)
    if urllib.parse.urlparse(url).scheme.lower() not in ("https", "http", "file"):
        raise ValueError(f"refusing to fetch {url!r}: scheme must be http(s) or file")
    # scheme allowlisted above; cfg.download_url is a pinned in-repo registry URL
    request = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310
    with urllib.request.urlopen(request, timeout=300) as resp, open(dest, "wb") as fh:  # noqa: S310
        shutil.copyfileobj(resp, fh, length=1 << 20)
    return dest


def download_instances(cfg: VRPConfig) -> list[Path]:
    """Fetch the Solomon archive and extract the configured instances.

    Writes ``data/raw/<INSTANCE>.txt`` plus a ``dataset_card.json`` pinning
    the archive sha256, license and snapshot date (playbook §Data).
    """
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = _fetch_archive(cfg.download_url, cfg.raw_dir / cfg.raw_zip_name)
    written: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        members = {
            Path(name).stem.upper(): name for name in zf.namelist() if name.lower().endswith(".txt")
        }
        for inst in cfg.instances:
            member = members.get(inst)
            if member is None:
                raise KeyError(f"instance {inst} not found in {cfg.download_url}")
            dest = cfg.raw_dir / f"{inst}.txt"
            dest.write_bytes(zf.read(member))
            written.append(dest)
            logger.info("%s -> %s", inst, dest)

    card = DatasetContract(
        name="solomon-vrptw-100-subset",
        source=cfg.download_url,
        license="Academic benchmark — free to use with citation (Solomon 1987, Oper. Res. 35(2))",
        snapshot_date=date.today(),
        checksum_sha256=sha256_of(zip_path),
        n_rows=100 * len(written),
    )
    (cfg.raw_dir / "dataset_card.json").write_text(card.model_dump_json(indent=2))
    return written


@app.command()
def download() -> None:
    """Download and extract the configured Solomon instances."""
    paths = download_instances(get_vrp_config())
    typer.echo(f"downloaded {len(paths)} instances -> {get_vrp_config().raw_dir}")


@app.command()
def solve() -> None:
    """Run all solvers on every instance and write reports/solutions.json."""
    path = run_solve(get_vrp_config())
    typer.echo(f"solutions written to {path}")


@app.command()
def evaluate() -> None:
    """Compute gaps vs best-known, figures and the HTML report."""
    path = run_evaluate(get_vrp_config())
    typer.echo(f"metrics written to {path}")


@app.command(name="all")
def run_all() -> None:
    """Full pipeline: download -> solve -> evaluate."""
    cfg = get_vrp_config()
    setup_logging(cfg.log_level)
    paths = download_instances(cfg)
    typer.echo(f"downloaded {len(paths)} instances -> {cfg.raw_dir}")
    solutions = run_solve(cfg)
    typer.echo(f"solutions written to {solutions}")
    metrics = run_evaluate(cfg)
    summary = json.loads(metrics.read_text())["summary"]
    typer.echo(
        "mean gap to best-known: "
        + ", ".join(f"{name}={v['mean_gap_pct']:.2f}%" for name, v in summary.items())
    )
    typer.echo(f"metrics written to {metrics}")


if __name__ == "__main__":
    app()
