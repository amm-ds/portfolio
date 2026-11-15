"""FastAPI app for the eval-workbench: read-only dataset registry + run review.

The browser never executes models, alters expected outputs, or synthesizes
aggregate metrics — these endpoints only serve the registry and run history.
"""

from __future__ import annotations

from fastapi import FastAPI

from eval_workbench.routes import router

app = FastAPI(
    title="eval-workbench",
    description="Versioned dataset registry and evaluation review workbench.",
    version="0.1.0",
)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, bool]:
    return {"ready": True}
