# Multi-stage image: React/TS web build → uv workspace runtime (FastAPI).
#
# The image serves the showcase app (API + static web). Figure specs
# (projects/*/reports/figures/) and serving bundles
# (projects/*/reports/models/serving/) are committed to git, so every build —
# fresh clone or CI — ships a fully functional app; no `dvc pull` needed. The
# 01 RAG demo is the one opt-in exception and is NOT baked: neither the
# retrieval index (run `dvc repro` in projects/01-rag-agent on the host) nor
# the `rag_agent` package itself (the venv installs only showcase-api and its
# dependency subtree — see the uv sync step below). With the index mounted
# and RAG_CHAT_ENABLED=1, /rag/chat still fails closed with a 503 until the
# package is present; set LLM_* env for a live provider (HF embedding models
# download on first request, ~200 MB). Bulky raw data stays DVC-tracked and
# regenerates authoritatively via `dvc repro` — see
# docs/runbooks/pipeline-restore.md and deploy/DEPLOY.md.

# Base images pinned by digest (multi-arch manifest-list digests, so builds
# stay reproducible on both amd64 and arm64). Bump deliberately, not casually.
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS web
WORKDIR /web
COPY apps/showcase-web/package.json apps/showcase-web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/showcase-web/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58 AS runtime
WORKDIR /app

# libgomp1: lightgbm/xgboost native libs link OpenMP — without it the serving
# artifacts (joblib pickles) fail to unpickle in the image (OSError libgomp).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

# Workspace manifests + sources (members: libs/*, projects/*, apps/showcase-api).
# .dockerignore strips what the image neither installs nor serves (tests,
# notebooks, docs, data, caches), so these layers carry only build sources
# (src/, pyproject.toml) and the committed serving artifacts (reports*/).
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY projects projects
COPY apps/showcase-api apps/showcase-api

# Install ONLY showcase-api and its dependency subtree (workspace members
# 02/05/06 + libs/portfolio-{core,eval}); the other project packages (and
# their heavy deps: transformers, torch/stack, ragas, dvc, ...) stay out of
# the image — ~140 fewer distributions. This is a build-time flag only: the
# lockfile and the dev flow (`uv sync --all-packages`) are unaffected.
RUN uv sync --package showcase-api --no-dev

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
