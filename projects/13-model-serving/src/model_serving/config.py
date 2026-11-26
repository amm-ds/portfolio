"""Validated configuration for the model serving & Docker deployment study.

Playbook convention (ADR-0002): tunable numbers live in pydantic config
models, not as module-level constants. ``ServingConfig`` is the single source
of truth for the served-model re-derivation (experiment 12's committed v2
recipe: LightGBM under timestamp lags and keep-higher-MI pruning), the ONNX
export + parity gate, the serving app, the benchmark harness, the Docker
stage and the cost framing.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # re-exported (no stubs in repo)
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field, field_validator

__all__ = ["BenchConfig", "CostConfig", "LGBMConfig", "ServeConfig", "ServingConfig", "yaml"]


class LGBMConfig(PortfolioBaseModel):
    """LightGBM training knobs — identical to experiment 12's committed v2 params."""

    n_estimators: int = Field(
        default=1500, ge=10, description="Round cap; early stopping picks the rest."
    )
    early_stopping: int = Field(default=50, ge=5)
    hpo_trials: int = Field(default=50, ge=5, description="Optuna trial cap for the seeded study.")
    hpo_time_budget_s: int = Field(
        default=240, ge=10, description="Optuna study timeout (seconds) — the binding budget."
    )


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
    # Experiment 12's committed v2 recipe (params.yaml): date-aware timestamp
    # lags and keep-higher-MI pruning. The v1 behavior (positional lags,
    # drop-higher-MI) is preserved in 12's params_v1.yaml and previous_runs.v1.
    lag_mode: str = Field(default="timestamp", pattern="^(positional|timestamp)$")
    pruning_rule: str = Field(default="keep_higher_mi", pattern="^(drop_higher_mi|keep_higher_mi)$")
    champion_expected_test_mae: float = Field(
        default=23.76360139335002,
        gt=0.0,
        description="Experiment 12's committed v2 LightGBM test MAE (scored once).",
    )
    comparison_mlp_test_mae: float = Field(
        default=27.161182233265468,
        gt=0.0,
        description=(
            "Experiment 12's committed v2 MLP test MAE — the served model's "
            "validation runner-up, cited as the comparison (not re-trained here)."
        ),
    )
    reproduction_tolerance: float = Field(default=0.05, gt=0.0)
    lgbm: LGBMConfig = Field(default_factory=LGBMConfig)
    onnx_opset: int = Field(default=15, ge=15, le=22)
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
