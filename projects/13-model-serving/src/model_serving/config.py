"""Validated configuration for the model serving & Docker deployment study.

Playbook convention (ADR-0002): tunable numbers live in pydantic config
models, not as module-level constants. ``ServingConfig`` is the single source
of truth for the champion re-derivation (experiment 12's committed recipe),
the ONNX export + parity gate, the serving app, the benchmark harness, the
Docker stage and the cost framing.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # re-exported (no stubs in repo)
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator

__all__ = ["BenchConfig", "CostConfig", "MLPConfig", "ServeConfig", "ServingConfig", "yaml"]


class MLPConfig(PortfolioBaseModel):
    """Tabular MLP hyperparameters — identical to experiment 12's committed params."""

    hidden_dims: list[int] = Field(default=[64, 32], min_length=1)
    embed_dim: int = Field(default=8, ge=2)
    dropout: float = Field(default=0.2, ge=0.0, lt=1.0)
    weight_decay: float = Field(default=1e-4, ge=0.0)
    learning_rate: float = Field(default=1e-3, gt=0.0)
    batch_size: int = Field(default=256, ge=16)
    max_epochs: int = Field(default=150, ge=1)
    patience: int = Field(default=10, ge=1)
    huber_delta: float = Field(default=1.0, gt=0.0)


class ServeConfig(PortfolioBaseModel):
    """Project-local FastAPI service bind + readiness probe."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8137, ge=1024, le=65535)
    ready_timeout_s: float = Field(default=60.0, gt=0.0)


class BenchConfig(PortfolioBaseModel):
    """Async load-driver protocol (experiment 08's scored-once discipline)."""

    concurrency_levels: list[int] = Field(default=[1, 4, 16, 64], min_length=1)
    requests_per_concurrency: int = Field(default=300, ge=10)
    warmup_requests: int = Field(default=20, ge=0)
    repeats: int = Field(default=3, ge=1, description="Median-of-repeats per cell.")
    batch_sizes: list[int] = Field(default=[1, 8, 32, 128], min_length=1)
    batch_requests_per_size: int = Field(default=60, ge=5)
    request_timeout_s: float = Field(default=30.0, gt=0.0)
    rss_probes: int = Field(default=3, ge=1, description="Fresh-process RSS probes per backend.")

    @field_validator("concurrency_levels", "batch_sizes")
    @classmethod
    def _positive_distinct_sorted(cls, v: list[int]) -> list[int]:
        if any(x < 1 for x in v):
            raise ValueError("levels/sizes must be >= 1")
        return sorted(set(v))


class CostConfig(PortfolioBaseModel):
    """Declared assumptions for the electricity cost framing (same as 08's)."""

    usd_per_kwh: float = Field(default=0.30, gt=0.0)
    system_load_watts: float = Field(
        default=65.0,
        gt=0.0,
        description="Declared laptop draw while serving this API (no wall meter — an assumption).",
    )


class ServingConfig(PortfolioBaseModel):
    """Configuration for the full serving study (train → benchmark → docker → report)."""

    seed: int = Field(default=42)
    data_source: str = Field(default="uci", pattern="^(uci|synthetic)$")
    uci_source: str = Field(
        default="https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip"
    )
    uci_sha256: str = Field(
        default="b70182d0d0508e9abbb79306ce5c0cec34869000f8220175ac83d11dbe845401",
        min_length=64,
        max_length=64,
    )
    val_weeks: int = Field(default=8, ge=1)
    test_weeks: int = Field(default=8, ge=1)
    lag_hours: list[int] = Field(default=[1, 24, 168], min_length=1)
    corr_threshold: float = Field(default=0.9, gt=0.0, lt=1.0)
    ridge_alpha: float = Field(default=1.0, gt=0.0)
    champion_expected_test_mae: float = Field(
        default=25.43163249606178,
        gt=0.0,
        description="Experiment 12's committed champion test MAE (scored once).",
    )
    reproduction_tolerance: float = Field(default=0.05, gt=0.0)
    mlp: MLPConfig = Field(default_factory=MLPConfig)
    onnx_opset: int = Field(default=17, ge=15, le=22)
    parity_tolerance: float = Field(default=1e-4, gt=0.0)
    probe_grid_n: int = Field(default=512, ge=16)
    serve: ServeConfig = Field(default_factory=ServeConfig)
    bench: BenchConfig = Field(default_factory=BenchConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    image_repo: str = Field(default="portfolio-model-serving")
    image_tag: str = Field(default="13")

    @property
    def max_lag(self) -> int:
        """Largest lag horizon — the first train rows sacrificed to NaN lags."""
        return max(self.lag_hours)

    @property
    def image_ref(self) -> str:
        return f"{self.image_repo}:{self.image_tag}"


def load_config(path: Path = Path("params.yaml")) -> ServingConfig:
    """ServingConfig defaults overlaid with ``params.yaml`` when present (DVC)."""
    if not path.exists():
        return ServingConfig()
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ServingConfig(**data)
