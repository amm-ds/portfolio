"""Data models for the eval-workbench: datasets, runs, and per-case results.

The workbench is deliberately read-only: the browser never executes models,
alter expected outputs, or synthesize aggregate metrics. The models below
are the fixed API contract shared by the backend and the frontend.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetRecord(BaseModel):
    """One versioned evaluation dataset."""

    id: str
    name: str
    version: str
    n_cases: int = Field(ge=0)
    description: str = ""
    created_at: str = ""


class CaseResult(BaseModel):
    """One case's outcome inside a run."""

    id: str
    question: str
    expected: str
    actual: str
    passed: bool
    error: str | None = None  # execution failure, distinct from a wrong answer
    latency_ms: float = Field(ge=0)


class EvalRunSummary(BaseModel):
    """One model run over a dataset version."""

    id: str
    dataset_id: str
    model: str
    completed: bool
    n_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)  # execution failures, not wrong answers
    accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    f1: float | None = Field(default=None, ge=0.0, le=1.0)
    p95_latency_ms: float | None = Field(default=None, ge=0.0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    started_at: str = ""
    cases: list[CaseResult] = Field(default_factory=list)
