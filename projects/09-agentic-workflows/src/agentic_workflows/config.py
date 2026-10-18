"""Configuration: pydantic models only — no constants in logic.

``EvalConfig`` mirrors ``params.yaml`` field for field so the DVC stages and
the CLI stay in sync with the code (platform convention, ADR-0002).

``Settings`` re-points the platform env file at the monorepo root: suite runs
start in the project directory, and the hosted-provider credentials and budget
env vars live in the gitignored root ``.env`` (never committed, never printed).
"""

from functools import lru_cache
from pathlib import Path

from portfolio_core.config import Settings as CoreSettings
from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field
from pydantic_settings import SettingsConfigDict

# src/agentic_workflows/config.py → project dir → projects/ → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(CoreSettings):
    """Project settings: platform env handling, env file at the monorepo root."""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so repeated calls share one validated instance."""
    return Settings()


class EvalConfig(PortfolioBaseModel):
    """Tunables for the workflow, suite and reporting.

    Every field must exist in ``params.yaml`` (defaults apply when the file
    is absent or a key is missing).
    """

    seed: int = Field(default=42, description="Reserved for corpus/sampling extensions.")
    max_execute_retries: int = Field(default=1, ge=0)
    max_critique_loops: int = Field(default=1, ge=0)
    suite_latency_budget_s: float = Field(default=180.0, gt=0)
    task_cost_limit_usd: float = Field(
        default=0.25,
        gt=0,
        description="Per-task cloud-equivalent cap; the run aborts mid-task past it.",
    )

    # Cloud-equivalent reference rate card ($1.00/Mtok in, $4.00/Mtok out —
    # the public kimi-k2.8-preview card; the hosted key is membership-quota).
    usd_per_mtok_input: float = Field(default=1.00, gt=0)
    usd_per_mtok_output: float = Field(default=4.00, gt=0)

    tasks_path: Path = Path("data/tasks.json")
    records_path: Path = Path("data/run_records.json")
    heldout_tasks_path: Path = Path("data/tasks_heldout.json")
    heldout_records_path: Path = Path("data/heldout_records.json")
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
