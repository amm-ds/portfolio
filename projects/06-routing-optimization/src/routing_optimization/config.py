"""Configuration for the routing-optimization showcase (ADR-0002, playbook §Config).

Every tunable lives on :class:`VRPConfig`; logic modules take values from an
instance of this model instead of reading module-level constants.
"""

from functools import lru_cache
from pathlib import Path

from portfolio_core.config import Settings
from pydantic import Field

from routing_optimization.schemas import Acceptance, AlnsInit


def default_instances() -> list[str]:
    """The full Solomon 100-customer benchmark (56 instances, all families)."""
    return [
        *(f"C1{i:02d}" for i in range(1, 10)),
        *(f"C2{i:02d}" for i in range(1, 9)),
        *(f"R1{i:02d}" for i in range(1, 13)),
        *(f"R2{i:02d}" for i in range(1, 12)),
        *(f"RC1{i:02d}" for i in range(1, 9)),
        *(f"RC2{i:02d}" for i in range(1, 9)),
    ]


def default_alns_hpo_instances() -> list[str]:
    """Representative subset used to tune ALNS knobs (one per family class)."""
    return ["C101", "C104", "R104", "R108", "RC104", "RC105"]


def default_best_known_path() -> Path:
    """Repo-local best-known table shipped by the data registry."""
    return (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "data-registry"
        / "best_known"
        / "solomon100.csv"
    )


def default_supplement_path() -> Path:
    """Project-local supplement covering the 43 instances the registry CSV
    does not list (values from the published SINTEF TOP table)."""
    return Path(__file__).resolve().parents[2] / "best_known_supplement.csv"


def default_acceptance_choices() -> list[Acceptance]:
    """Candidate acceptance rules sampled by the HPO search."""
    return ["first", "best"]


def default_alns_init_choices() -> list[AlnsInit]:
    """Candidate ALNS initial operator-weight pools sampled by the HPO search."""
    return ["uniform", "biased"]


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
    best_known_supplement_path: Path = Field(default_factory=default_supplement_path)
    max_two_opt_iterations: int = Field(
        default=200, ge=1, description="Global cap on accepted 2-opt moves across all routes."
    )
    map_instance: str = Field(default="C101", description="Instance drawn in the route-map figure.")
    solver_names: list[str] = Field(
        default_factory=lambda: ["nearest_neighbor", "clarke_wright", "two_opt"],
        description="Base solvers benchmarked per instance; two_opt polishes the better base plan.",
    )
    hpo_trials: int = Field(default=24, ge=1, description="Seeded random-search trials for HPO.")
    hpo_budget_choices: list[int] = Field(
        default_factory=lambda: [50, 100, 200, 500],
        description="Candidate 2-opt move budgets sampled by the HPO search.",
    )
    hpo_acceptance_choices: list[Acceptance] = Field(
        default_factory=default_acceptance_choices,
        description="Candidate acceptance rules sampled by the HPO search.",
    )
    hpo_tail_exchange_choices: list[bool] = Field(
        default_factory=lambda: [True, False],
        description="Candidate tail-exchange (2-opt*) on/off sampled by the HPO search.",
    )
    hpo_restart_choices: list[int] = Field(
        default_factory=lambda: [1, 2, 3, 4, 6, 8],
        description="Candidate best-of-k randomized-restart portfolio sizes.",
    )
    convergence_instances: list[str] = Field(
        default_factory=lambda: ["C101", "RC105"],
        description="Instances drawn in the convergence figures.",
    )
    alns_max_iterations: int = Field(
        default=120, ge=1, description="ALNS iteration cap (bounds runtime per instance)."
    )
    ortools_time_limit_s: float = Field(
        default=10.0,
        gt=0,
        description="CP-SAT wall-time limit per instance (external-reference solver).",
    )
    ortools_max_vehicles: int = Field(
        default=20,
        ge=1,
        description="CP-SAT fleet bound; the model fleet is min(instance fleet, "
        "max(this, hint fleet)) so the hinted incumbent always fits.",
    )
    ortools_fleet_slack: int = Field(
        default=3,
        ge=0,
        description="CP-SAT model fleet = hinted fleet + this slack (capped by "
        "ortools_max_vehicles and the instance fleet).",
    )
    alns_destroy_q: int = Field(
        default=10, ge=1, description="Customers removed per ALNS destroy operation."
    )
    alns_hpo_trials: int = Field(
        default=12, ge=1, description="Seeded search trials for ALNS knobs."
    )
    alns_hpo_instances: list[str] = Field(
        default_factory=default_alns_hpo_instances,
        description="Instances the ALNS knob search is evaluated on (representative subset).",
    )
    alns_segment_choices: list[int] = Field(
        default_factory=lambda: [25, 50, 100],
        description="Candidate ALNS segment lengths sampled by the HPO search.",
    )
    alns_reaction_choices: list[float] = Field(
        default_factory=lambda: [0.1, 0.3, 0.5],
        description="Candidate ALNS reaction factors sampled by the HPO search.",
    )
    alns_init_choices: list[AlnsInit] = Field(
        default_factory=default_alns_init_choices,
        description="Candidate ALNS initial operator weights sampled by the HPO search.",
    )
    params_path: Path | None = Field(
        default=None,
        description="Override for the params.yaml the solve stage writes "
        "(tests point this at a tmp file; default: the project params.yaml).",
    )


@lru_cache
def get_vrp_config() -> VRPConfig:
    """Cached accessor shared by CLI commands and tests."""
    return VRPConfig()
