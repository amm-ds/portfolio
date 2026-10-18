# Multi-stage image: React/TS web build → uv workspace runtime (FastAPI).
#
# The image serves the showcase app (API + static web). Figure specs
# (projects/*/reports/figures/) and serving bundles
# (projects/*/reports/models/serving/) are committed to git, so every build —
# fresh clone or CI — ships a fully functional app; no `dvc pull` needed. The
# 01 RAG retrieval index is the one opt-in exception and is NOT baked: enable
# /rag/chat by running `dvc repro` in projects/01-rag-agent on the host
# (offline mock provider by default; set LLM_* env for a live provider — HF
# embedding models download on first request, ~200 MB). Bulky raw data stays
# DVC-tracked and regenerates authoritatively via `dvc repro` — see
# docs/runbooks/pipeline-restore.md and deploy/DEPLOY.md.

FROM node:22-alpine AS web
WORKDIR /web
COPY apps/showcase-web/package.json apps/showcase-web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/showcase-web/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
WORKDIR /app

# libgomp1: lightgbm/xgboost native libs link OpenMP — without it the serving
# artifacts (joblib pickles) fail to unpickle in the image (OSError libgomp).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

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

# Non-root runtime user
RUN useradd --system --create-home app && chown -R app /app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"

# Trust proxy headers only from explicitly allowed IPs (loopback by default;
# the prod compose network sets FORWARDED_ALLOW_IPS to its Caddy container so
# the rate limiter keys on real clients, not the proxy — see deploy/).
CMD ["sh", "-c", "uvicorn showcase_api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
