"""Typed contracts for this project (ADR-0002)."""

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field


class ExampleRecord(PortfolioBaseModel):
    """One validated record — replace with the project's real schema."""

    id: str = Field(min_length=1)
