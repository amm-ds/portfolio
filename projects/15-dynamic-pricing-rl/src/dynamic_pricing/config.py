"""Configuration: pydantic models only — no constants in logic."""

from portfolio_core.config import Settings as CoreSettings
from portfolio_core.schemas import PortfolioBaseModel


class Settings(CoreSettings):
    """Project settings (env handling inherited from the platform)."""


class ProjectConfig(PortfolioBaseModel):
    """Tunables for this project. Mirror every field in params.yaml."""

    seed: int = 42
