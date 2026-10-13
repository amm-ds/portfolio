"""Typed configuration for the mobility pipeline (playbook §Config).

Every knob lives on a pydantic model with a documented default; nothing is
hardcoded in logic. ``params.yaml`` mirrors :class:`MobilityConfig` so DVC
can track parameter changes and rebuild downstream stages.
"""

from datetime import date
from pathlib import Path

from portfolio_core.config import Settings as BaseSettings
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field

#: Absolute path to the project directory (…/projects/07-open-data-mobility),
#: so the pipeline behaves identically from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
NOAA_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/USW00094728.csv.gz"


class Settings(BaseSettings):
    """Project settings extending the platform root (ADR-0002)."""

    data_dir: Path = PROJECT_ROOT / "data"
    reports_dir: Path = PROJECT_ROOT / "reports"


class GBMConfig(PortfolioBaseModel):
    """HistGradientBoostingRegressor knobs (mean and p90 quantile models)."""

    max_iter: int = 300
    learning_rate: float = 0.08
    max_leaf_nodes: int = 63
    min_samples_leaf: int = 40
    l2_regularization: float = 1.0
    quantile_max_iter: int = 200


class NNConfig(PortfolioBaseModel):
    """TemporalNet knobs: small MLP, hand-written loop, laptop-friendly."""

    hidden_size: int = 64
    second_hidden_size: int = 32
    epochs: int = 8
    batch_size: int = 1024
    lr: float = 1e-3
    weight_decay: float = 1e-5
    grad_clip: float = 5.0
    early_stop_patience: int = 2


class HPOConfig(PortfolioBaseModel):
    """Optuna studies: bounded trials, seeded, validation = embargoed fold."""

    gbm_trials: int = 30
    nn_trials: int = 10
    #: Fit-row budget per trial (most-recent slice of the train window only;
    #: the Oct-Dec test window is never touched). None = all train rows.
    max_fit_rows: int | None = 500_000
    #: Row budget for permutation-importance scoring at evaluate time.
    perm_importance_rows: int = 200_000


class MobilityConfig(PortfolioBaseModel):
    """Everything the pipeline needs, in one validated document."""

    # Sources
    months: list[str] = Field(
        default_factory=lambda: [
            "2024-01",
            "2024-02",
            "2024-03",
            "2024-04",
            "2024-05",
            "2024-06",
            "2024-07",
            "2024-08",
            "2024-09",
            "2024-10",
            "2024-11",
            "2024-12",
        ]
    )
    tlc_base_url: str = TLC_BASE_URL
    zone_lookup_url: str = ZONE_LOOKUP_URL
    noaa_url: str = NOAA_URL

    # Paths (absolute, anchored at the project root)
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    validated_dir: Path = PROJECT_ROOT / "data" / "validated"
    curated_dir: Path = PROJECT_ROOT / "data" / "curated"
    features_dir: Path = PROJECT_ROOT / "data" / "features"
    reports_dir: Path = PROJECT_ROOT / "reports"

    # Bounded slice & DQ gates
    max_rows_per_month: int | None = Field(default=None, description="None = all rows")
    min_rows_per_month: int = 500_000
    #: Freshness gate: newest pickup must be within this many days of month end.
    freshness_slack_days: int = 1

    # Trip filters (join stage)
    min_duration_min: float = 1.0
    max_duration_min: float = 240.0

    # Feature engineering
    lags: list[int] = Field(default_factory=lambda: [1, 2, 24, 168])
    train_cutoff: date = date(2024, 10, 1)

    # Model budgets
    max_train_rows: int = 2_000_000
    gbm: GBMConfig = Field(default_factory=GBMConfig)
    nn: NNConfig = Field(default_factory=NNConfig)
    hpo: HPOConfig = Field(default_factory=HPOConfig)
    seed: int = 42

    @property
    def tlc_raw_dir(self) -> Path:
        return self.raw_dir / "tlc"

    @property
    def checksum_registry(self) -> Path:
        return self.raw_dir / "checksums.json"

    @property
    def contract_dir(self) -> Path:
        return self.raw_dir / "contracts"

    @property
    def zone_hour_demand_path(self) -> Path:
        return self.curated_dir / "zone_hour_demand.parquet"

    @property
    def zones_path(self) -> Path:
        return self.curated_dir / "zones.parquet"

    @property
    def weather_path(self) -> Path:
        return self.curated_dir / "weather.parquet"

    @property
    def models_dir(self) -> Path:
        return self.reports_dir / "models"


_DEFAULT_CONFIG: MobilityConfig | None = None


def get_config() -> MobilityConfig:
    """Cached accessor (mirrors ``portfolio_core.config.get_settings``)."""
    global _DEFAULT_CONFIG
    if _DEFAULT_CONFIG is None:
        _DEFAULT_CONFIG = MobilityConfig()
    return _DEFAULT_CONFIG
