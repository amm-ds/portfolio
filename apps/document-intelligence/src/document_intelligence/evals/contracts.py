"""Strict, versioned page-level ground-truth contracts for evaluation."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from document_intelligence.domain.base import StrictModel

DEFAULT_REFERENCE_PATH = Path(__file__).resolve().parents[3] / "evaluations" / "references.json"
DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures"


class ReferenceKeyPoint(StrictModel):
    text: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)


class ReferenceEntity(StrictModel):
    text: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class ReferenceTopic(StrictModel):
    label: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class ReferenceQuestion(StrictModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    citations: list[str] = Field(min_length=1)


class ReferencePage(StrictModel):
    page: int = Field(ge=1)
    key_points: list[ReferenceKeyPoint] = Field(default_factory=list)
    entities: list[ReferenceEntity] = Field(default_factory=list)
    topics: list[ReferenceTopic] = Field(default_factory=list)
    questions: list[ReferenceQuestion] = Field(default_factory=list)
    expect_tables: int = Field(default=0, ge=0)
    expect_images: int = Field(default=0, ge=0)


class ReferenceCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9-]+$")
    file: str = Field(min_length=1)
    pages: list[ReferencePage] = Field(min_length=1)


class EvaluationReferences(StrictModel):
    schema_version: Literal["page-analysis-eval-v1"]
    dataset_revision: str
    description: str
    summary_method: str
    answer_method: str
    topic_method: str
    entity_method: str
    miss_method: str
    cases: list[ReferenceCase] = Field(min_length=1)


def load_references(path: Path = DEFAULT_REFERENCE_PATH) -> EvaluationReferences:
    """Validate references before any provider call or report is produced."""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    return EvaluationReferences.model_validate(payload)
