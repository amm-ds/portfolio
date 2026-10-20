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

# tape-forecast demo payload (separate repo, pinned tag). The Python package
# itself arrives via the git dependency in apps/showcase-api (uv sync below);
# this stage only supplies what git does not carry into the wheel: the serving
# parquets, Phase 1 reports and the built demo SPA. Mounted by showcase_api
# main at /demos/tape-forecast via TAPE_FORECAST_* env vars.
FROM node:22-alpine AS tape-demo
WORKDIR /tape
RUN apk add --no-cache git \
    && git clone --depth 1 --branch v0.2.0 https://github.com/amm-ds/tape-forecast-demo.git .
WORKDIR /tape/web
RUN npm ci --no-audit --no-fund && npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
WORKDIR /app

# libgomp1: lightgbm/xgboost native libs link OpenMP — without it the serving
# artifacts (joblib pickles) fail to unpickle in the image (OSError libgomp).
# git: uv resolves the tape-forecast git dependency at sync time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 git \
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

# tape-forecast demo payload (data + reports + built SPA — see tape-demo stage)
COPY --from=tape-demo /tape/data /opt/tape-forecast/data
COPY --from=tape-demo /tape/reports /opt/tape-forecast/reports
COPY --from=tape-demo /tape/web/dist /opt/tape-forecast/web/dist
ENV TAPE_FORECAST_SERVING_DIR=/opt/tape-forecast/data/serving \
    TAPE_FORECAST_REPORTS_DIR=/opt/tape-forecast/reports \
    TAPE_FORECAST_WEB_DIST=/opt/tape-forecast/web/dist \
    TAPE_FORECAST_LAB_DIR=/opt/tape-forecast/data/lab

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
