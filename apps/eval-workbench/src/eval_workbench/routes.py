"""Shared workbench routes — mounted by the standalone app AND showcase-api.

Both apps serve the same read-only contract: /datasets, /runs, /runs/{id}.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from eval_workbench.models import DatasetRecord, EvalRunSummary
from eval_workbench.registry import Registry

router = APIRouter()
_registry = Registry()


@router.get("/datasets", response_model=list[DatasetRecord])
def datasets() -> list[DatasetRecord]:
    return _registry.datasets()


@router.get("/runs", response_model=list[EvalRunSummary])
def runs() -> list[EvalRunSummary]:
    return _registry.runs()


@router.get("/runs/{run_id}", response_model=EvalRunSummary)
def run_detail(run_id: str) -> EvalRunSummary:
    run = _registry.run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    return run
