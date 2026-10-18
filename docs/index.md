# Portfolio documentation

End-to-end ML/AI engineering portfolio: reproducible DVC pipelines, typed
contracts, agentic AI, and client-ready evaluation artifacts.

Use the navigation on the left: architecture decision records, the engineering
playbook, per-project design documents, the open-data registry, and operational
runbooks.

## Quick start

```bash
make setup          # uv sync + pre-commit
make test           # ruff + mypy + pytest with coverage gates
dvc repro           # reproduce all pipelines (downloads public data)
make docs-serve     # docs at http://127.0.0.1:8000
make docker-up      # showcase app (FastAPI + React) at http://localhost:8000 —
                    # serves the real artifacts: forecast/score/solve endpoints,
                    # per-project story/metrics/figures, RAG chat
```
