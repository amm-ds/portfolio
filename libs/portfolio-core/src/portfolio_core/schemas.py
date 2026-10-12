"""Base contracts every dataset and run validates against (ADR-0002)."""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SHA256_RE = r"^[0-9a-f]{64}$"


class PortfolioBaseModel(BaseModel):
    """Shared model config: strict typing everywhere in the platform."""

    model_config = ConfigDict(frozen=False, extra="forbid", str_strip_whitespace=True)


class DatasetContract(PortfolioBaseModel):
    """Versioned identity card for a dataset (real or synthetic)."""

    name: str = Field(min_length=1)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    source: str = Field(description="URL or 'synthetic://<generator>'")
    license: str = Field(description="SPDX id or license text")
    snapshot_date: date
    checksum_sha256: str = Field(pattern=_SHA256_RE)
    n_rows: int = Field(ge=0)

    @field_validator("checksum_sha256", mode="before")
    @classmethod
    def _lower_hex(cls, v: Any) -> Any:
        return v.lower() if isinstance(v, str) else v


class RunConfig(PortfolioBaseModel):
    """Base run configuration: seed + artifact locations."""

    seed: int = 42
    data_dir: str = "data"
    reports_dir: str = "reports"


class MetricValue(PortfolioBaseModel):
    """One named, comparable metric reading."""

    name: str
    value: float
    split: str = "test"
    higher_is_better: bool = True
