"""Central settings. Every project extends :class:`Settings` rather than
redefining env handling (ADR-0002, playbook §Config)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root settings; project-specific settings subclass this."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    # Reproducibility
    seed: int = Field(default=42, description="Global random seed for synthetic data and training.")

    # Paths
    data_dir: Path = Field(default=Path("data"), description="Root for downloaded/prepared data.")
    reports_dir: Path = Field(default=Path("reports"), description="Root for evaluation artifacts.")

    # LLM provider (ADR-0004): OpenAI-compatible endpoint, mock when unset.
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    llm_timeout: float = Field(default=60.0, gt=0, alias="LLM_TIMEOUT")

    # LLM budget & cost metering (labelled cloud-equivalent estimates; the hosted
    # key is membership-quota, not pay-per-token — see portfolio_core.llm_budget).
    llm_cost_limit_usd: float = Field(default=3.0, gt=0, alias="LLM_COST_LIMIT_USD")
    llm_suite_cost_limit_usd: float = Field(default=2.0, gt=0, alias="LLM_SUITE_COST_LIMIT_USD")
    llm_max_requests: int = Field(default=400, gt=0, alias="LLM_MAX_REQUESTS")
    llm_total_tokens_limit: int = Field(default=4_000_000, gt=0, alias="LLM_TOTAL_TOKENS_LIMIT")
    usd_per_mtok_input: float | None = Field(default=None, gt=0, alias="USD_PER_MTOK_INPUT")
    usd_per_mtok_output: float | None = Field(default=None, gt=0, alias="USD_PER_MTOK_OUTPUT")

    # Logging
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so repeated calls share one validated instance."""
    return Settings()
