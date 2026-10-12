# Runbook — pipeline restore (clean-clone reproduction)

**Goal:** a stranger on a fresh machine reproduces every headline result.

## Standard path

```bash
git clone https://github.com/amm-ds/portfolio.git && cd portfolio
make setup        # uv sync --all-packages --dev + pre-commit
dvc repro         # downloads pinned public data, runs all stages
```

## If a stage fails

1. **Checksum mismatch in `prepare`.** The upstream source changed. Do not
   bypass. Check the dataset card for a newer snapshot, update URL + checksum +
   snapshot date, and re-pin deliberately.
2. **OOM in Project 07.** The pipeline is designed for a laptop with ~8 GB free
   RAM (polars lazy/streaming, bounded slice). Close memory hogs; the bounded
   slice (12 months, yellow taxi) is the supported configuration.
3. **Network issues.** Stages are resumable; re-run `dvc repro`.
4. **Env/LLM.** Everything except the live RAG demo runs without an API key;
   the mock provider is the default. Set `LLM_BASE_URL`/`LLM_API_KEY` only for
   real-provider runs.

## Verify success

- Each project leaves `reports/metrics.json` + figures under `reports/figures/`.
- `make test` green.
- `make docker-up` → `http://localhost:8000/health` returns 200 and the
  showcase UI renders project results.
