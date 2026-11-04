# syntax=docker/dockerfile:1
# Multi-stage serving image for experiment 13 (model-serving).
#
# Build from the REPOSITORY ROOT (the uv workspace + uv.lock live there; the
# root .dockerignore keeps data/, .venv and caches out of the context):
#
#   docker build -f projects/13-model-serving/Dockerfile -t portfolio-model-serving:13 .
#
# The model is baked in: the docker stage stages data/models/ into
# image/serving/ (outside any dockerignored data/ path), copied to /app/models
# below. Runtime env picks the backend: SERVING_BACKEND=onnx (default) | native.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
# The venv is created at its FINAL path (/app/.venv): venv console scripts
# embed absolute shebangs, so building at a staging path and copying breaks.
WORKDIR /app

# Workspace skeleton — root manifest + lockfile + every member's sources so
# `uv sync --frozen` resolves exactly the committed lockfile.
COPY pyproject.toml uv.lock ./
COPY libs ./libs
COPY apps ./apps
COPY projects ./projects
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# --no-editable: the venv must be self-contained in the runtime stage.
RUN uv sync --frozen --no-dev --no-editable --package 13-model-serving

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN useradd --system --uid 10001 --create-home appuser
# --chown at COPY: a later `chown -R` would duplicate the whole venv into a
# new layer and double the image.
COPY --from=build --chown=appuser:appuser /app/.venv /app/.venv
# Staged by `python -m model_serving.cli docker` from data/models/ (mlp.pt,
# model.onnx, mlp_arch.json, mlp_meta.json, feature_contract.json).
COPY --chown=appuser:appuser projects/13-model-serving/image/serving /app/models
ENV PATH="/app/.venv/bin:$PATH" \
    MODELS_DIR=/app/models \
    SERVING_BACKEND=onnx \
    PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=25s --retries=8 \
  CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"]
CMD ["python", "-m", "uvicorn", "--factory", "--host", "0.0.0.0", "--port", "8000", "model_serving.service.app:create_app"]
