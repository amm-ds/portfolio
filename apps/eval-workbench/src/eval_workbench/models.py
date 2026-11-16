"""Data models for the eval-workbench — the exact contract the frontend consumes.

The browser never executes models, alters expected outputs, or synthesizes
aggregate metrics. Field names are pinned to the frontend's `api/types.ts`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetRecord(BaseModel):
    """One versioned evaluation dataset (frontend: `Dataset`)."""

    id: str
    name: str
    version: str
    description: str
    case_count: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""


class CaseResult(BaseModel):
    """One case's outcome inside a run (frontend: `RunCase`)."""

    id: str
    input: str
    expected: str
    output: str | None = None
    passed: bool
    latency_ms: float = Field(ge=0)
    error: str | None = None  # execution failure, distinct from a wrong answer


class RunMetrics(BaseModel):
    """Aggregate metrics for a completed run (frontend: `RunMetrics`)."""

    accuracy: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    p95_latency_ms: float = Field(ge=0.0)
    cost_usd: float = Field(ge=0.0)


class EvalRunSummary(BaseModel):
    """One model run over a dataset version (frontend: `RunSummary`)."""

    id: str
    dataset_id: str
    model: str
    status: str  # "queued" | "running" | "completed" | "failed"
    case_count: int = Field(ge=0)
    failed_cases: int = Field(ge=0)  # execution failures, not wrong answers
    metrics: RunMetrics | None = None
    created_at: str = ""
    completed_at: str | None = None
    cases: list[CaseResult] = Field(default_factory=list)
