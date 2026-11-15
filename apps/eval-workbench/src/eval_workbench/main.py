"""FastAPI app for the eval-workbench: read-only dataset registry + run review.

The browser never executes models, alters expected outputs, or synthesizes
aggregate metrics — these endpoints only serve the registry and run history.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from eval_workbench.models import DatasetRecord, EvalRunSummary
from eval_workbench.registry import Registry

app = FastAPI(
    title="eval-workbench",
    description="Versioned dataset registry and evaluation review workbench.",
    version="0.1.0",
)
_registry = Registry()


@app.get("/datasets", response_model=list[DatasetRecord])
def datasets() -> list[DatasetRecord]:
    return _registry.datasets()


@app.get("/runs", response_model=list[EvalRunSummary])
def runs() -> list[EvalRunSummary]:
    return _registry.runs()


@app.get("/runs/{run_id}", response_model=EvalRunSummary)
def run_detail(run_id: str) -> EvalRunSummary:
    run = _registry.run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown run {run_id!r}")
    return run


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, bool]:
    return {"ready": True}
