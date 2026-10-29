# Runbook — pipeline restore (clean-clone reproduction)

**Goal:** a stranger on a fresh machine reproduces every headline result.

## Standard path

```bash
git clone https://github.com/amm-ds/portfolio.git && cd portfolio
make setup        # uv sync --all-packages --dev + pre-commit
cd projects/02-demand-forecasting
uv run dvc repro  # downloads this project's pinned data and runs its stages
```

Run `uv run dvc repro` separately inside each project you need to restore;
there is no single root pipeline that reproduces all ten projects.

## If a stage fails

1. **Checksum mismatch in `prepare`.** The upstream source changed. Do not
   bypass. Check the dataset card for a newer snapshot, update URL + checksum +
   snapshot date, and re-pin deliberately.
2. **OOM in Project 07.** The pipeline is designed for a laptop with ~8 GB free
   RAM (polars lazy/streaming, bounded slice). Close memory hogs; the bounded
   slice (12 months, yellow taxi) is the supported configuration.
3. **Network issues.** Stages are resumable; re-run `dvc repro`.
4. **Env/LLM.** Ordinary showcase endpoints need no API key. There is no
   production mock provider; an explicitly enabled Project 01 uses local Ollama
   unless `LLM_BASE_URL`/`LLM_API_KEY` configure a hosted provider.

## Verify success

- Each project leaves `reports/metrics.json` + figures under `reports/figures/`.
- From the repository root, `make test` is green.
- `make docker-up` → `http://localhost:8000/health` returns 200 with
  `"ready":true`, and the showcase UI renders project results.
