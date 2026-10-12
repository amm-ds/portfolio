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

    # Logging
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so repeated calls share one validated instance."""
    return Settings()
