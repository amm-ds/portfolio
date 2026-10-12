"""Configuration for the routing-optimization showcase (ADR-0002, playbook §Config).

Every tunable lives on :class:`VRPConfig`; logic modules take values from an
instance of this model instead of reading module-level constants.
"""

from functools import lru_cache
from pathlib import Path

from portfolio_core.config import Settings
from pydantic import Field


def default_instances() -> list[str]:
    """The curated Solomon 100-customer subset used by this showcase."""
    return ["C101", "C102", "C103", "C104", "C105", "RC102", "RC103", "RC104", "RC105", "RC108"]


def default_best_known_path() -> Path:
    """Repo-local best-known table shipped by the data registry."""
    return (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "data-registry"
        / "best_known"
        / "solomon100.csv"
    )


class VRPConfig(Settings):
    """VRPTW run configuration: instances, paths and solver limits."""

    instances: list[str] = Field(default_factory=default_instances)
    raw_dir: Path = Field(
        default=Path("data/raw"), description="Directory holding the raw .txt instances."
    )
    raw_zip_name: str = Field(default="solomon-100.zip", description="Downloaded archive name.")
    download_url: str = Field(
        default="https://www.sintef.no/globalassets/project/top/vrptw/solomon/solomon-100.zip",
        description="Backup mirror of the Solomon 100-customer instance definitions (SINTEF TOP).",
    )
    best_known_path: Path = Field(default_factory=default_best_known_path)
    max_two_opt_iterations: int = Field(
        default=200, ge=1, description="Global cap on accepted 2-opt moves across all routes."
    )
    map_instance: str = Field(default="C101", description="Instance drawn in the route-map figure.")
    solver_names: list[str] = Field(
        default_factory=lambda: ["nearest_neighbor", "clarke_wright", "two_opt"],
        description="Base solvers benchmarked per instance; two_opt polishes the better base plan.",
    )


@lru_cache
def get_vrp_config() -> VRPConfig:
    """Cached accessor shared by CLI commands and tests."""
    return VRPConfig()
