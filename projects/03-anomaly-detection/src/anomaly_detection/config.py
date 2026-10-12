"""Pydantic configuration for the anomaly-detection showcase.

All tunables live in :class:`AnomalyConfig` (playbook: constants only in
pydantic config models). Relative paths resolve against the project root so
the CLI behaves the same from any working directory.
"""

from datetime import date
from pathlib import Path
from typing import Literal

from portfolio_core.schemas import RunConfig
from pydantic import Field, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ModelName = Literal["isolation_forest", "lof", "ocsvm"]

ALLOWED_MODELS: tuple[str, ...] = ("isolation_forest", "lof", "ocsvm")
SIGNALS: tuple[str, ...] = ("cpu", "mem", "latency_ms")


class AnomalyConfig(RunConfig):
    """Run configuration for the telemetry anomaly-detection pipeline."""

    n: int = Field(default=20_000, gt=0, description="Number of synthetic telemetry rows.")
    anomaly_rate: float = Field(
        default=0.02, gt=0, lt=0.5, description="Injected anomaly fraction in the data."
    )
    contamination: float = Field(
        default=0.02,
        gt=0,
        lt=0.5,
        description="Assumed anomaly fraction used by detectors and the scoring threshold.",
    )
    models: list[ModelName] = Field(default=["isolation_forest", "lof", "ocsvm"])
    windows: list[int] = Field(
        default=[10, 60],
        min_length=1,
        description="Rolling-window sizes (in rows) for aggregate features.",
    )
    train_frac: float = Field(default=0.7, gt=0, lt=1, description="Time-ordered train split.")
    max_null_rate: float = Field(default=0.01, ge=0, lt=1, description="DQ gate per column.")
    n_estimators: int = Field(default=300, gt=0, description="IsolationForest trees.")
    lof_neighbors: int = Field(default=20, gt=0, description="LOF neighborhood size.")
    ocsvm_nu: float | None = Field(
        default=None,
        gt=0,
        lt=0.5,
        description="OneClassSVM nu; defaults to ``contamination`` when unset.",
    )
    snapshot_date: date = Field(
        default=date(2024, 1, 1), description="Snapshot date recorded on the dataset contract."
    )

    @field_validator("windows")
    @classmethod
    def _windows_positive(cls, v: list[int]) -> list[int]:
        if any(w <= 0 for w in v):
            raise ValueError("rolling windows must be positive")
        return v

    def resolve(self, path: str | Path) -> Path:
        """Resolve ``path`` against the project root unless already absolute."""
        p = Path(path)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def data_path(self) -> Path:
        """Directory for datasets and fitted models."""
        return self.resolve(self.data_dir)

    @property
    def reports_path(self) -> Path:
        """Directory for HTML/JSON evaluation artifacts."""
        return self.resolve(self.reports_dir)

    @property
    def raw_path(self) -> Path:
        return self.data_path / "raw.parquet"

    @property
    def features_path(self) -> Path:
        return self.data_path / "features.parquet"

    @property
    def contract_path(self) -> Path:
        return self.data_path / "dataset_contract.json"

    @property
    def models_dir(self) -> Path:
        return self.data_path / "models"

    @property
    def dq_report_path(self) -> Path:
        return self.reports_path / "dq_report.html"

    @property
    def eval_dir(self) -> Path:
        # Canonical location: the showcase API serves reports/metrics.json and
        # reports/report.html at the project reports root.
        return self.reports_path

    @property
    def figures_dir(self) -> Path:
        return self.reports_path / "figures"
