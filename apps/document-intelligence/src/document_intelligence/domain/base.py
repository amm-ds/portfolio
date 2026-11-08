"""Shared strict schema base."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject unknown fields at every trust boundary."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
