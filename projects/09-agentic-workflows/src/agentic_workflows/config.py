"""Configuration: pydantic models only — no constants in logic.

``EvalConfig`` mirrors ``params.yaml`` field for field so the DVC stages and
the CLI stay in sync with the code (platform convention, ADR-0002).
"""

from pathlib import Path

from portfolio_core.config import Settings as CoreSettings
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


class Settings(CoreSettings):
    """Project settings (env handling inherited from the platform)."""


class EvalConfig(PortfolioBaseModel):
    """Tunables for the workflow, suite and reporting.

    Every field must exist in ``params.yaml`` (defaults apply when the file
    is absent or a key is missing).
    """

    seed: int = Field(default=42, description="Reserved for corpus/sampling extensions.")
    max_execute_retries: int = Field(default=1, ge=0)
    max_critique_loops: int = Field(default=1, ge=0)
    suite_latency_budget_s: float = Field(default=180.0, gt=0)

    usd_per_mtok_input: float = Field(default=0.15, gt=0)
    usd_per_mtok_output: float = Field(default=0.60, gt=0)

    tasks_path: Path = Path("data/tasks.json")
    records_path: Path = Path("data/run_records.json")
    checkpoint_path: Path = Path("data/checkpoint.json")
    reports_dir: Path = Path("reports")


def load_config(path: Path = Path("params.yaml")) -> EvalConfig:
    """EvalConfig defaults overlaid with ``params.yaml`` when present (DVC)."""
    from portfolio_core.logging import get_logger

    logger = get_logger(__name__)
    if not path.exists():
        return EvalConfig()
    import yaml  # type: ignore[import-untyped]

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    known = {k: v for k, v in data.items() if k in EvalConfig.model_fields}
    unknown = sorted(set(data) - set(EvalConfig.model_fields))
    if unknown:
        logger.warning("params.yaml has keys outside EvalConfig, ignored: %s", unknown)
    return EvalConfig(**known)
