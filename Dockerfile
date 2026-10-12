# Multi-stage image: React/TS web build → uv workspace runtime (FastAPI).
#
# The image serves the showcase app (API + static web) with the RAG retrieval
# index baked in, so /rag/chat works immediately (offline mock provider by
# default; set LLM_* env for a live provider — HF embedding models download
# on first request, ~200 MB). Project *results* (reports/, figures) are baked
# when present and regenerated authoritatively by `dvc repro` — see
# docs/runbooks/pipeline-restore.md.

FROM node:22-alpine AS web
WORKDIR /web
COPY apps/showcase-web/package.json apps/showcase-web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/showcase-web/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

# Workspace manifests + sources (members: libs/*, projects/*, apps/showcase-api)
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY projects projects
COPY apps/showcase-api apps/showcase-api

RUN uv sync --all-packages --no-dev

COPY --from=web /web/dist apps/showcase-web/dist

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"

CMD ["uvicorn", "showcase_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
