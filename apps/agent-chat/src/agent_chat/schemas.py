"""Typed contracts shared across the agent, API, and evals.

Everything crossing a boundary (model output, tool results, API payloads) is
one of these models — no dicts at the seams.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """A grounded reference: where a claim came from and the exact words."""

    source: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Answer(BaseModel):
    """The agent's structured final output (``output_type``).

    ``citations`` must reference retrieved or skill-provided content, never
    the model's memory; ``uncertainty`` is the model's own calibration.
    """

    text: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    uncertainty: Literal["low", "medium", "high"] = "medium"


class SentMessage(BaseModel):
    """Record of a consequential message the agent posted after approval."""

    channel: str
    text: str
