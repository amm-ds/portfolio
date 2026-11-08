# syntax=docker/dockerfile:1
# Base images pinned by digest (multi-arch index, like deploy/docker-compose.prod.yml):
# tag-only pulls are mutable. Bump deliberately, not casually.
FROM ghcr.io/astral-sh/uv:0.5.31-python3.12-bookworm-slim@sha256:fef6dca3a45cd7ac8c4386e78263033ee4b262fe36c1ee077630e53ed6df2070 AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN uv sync --locked --no-dev

FROM python:3.12.9-slim@sha256:48a11b7ba705fd53bf15248d1f94d36c39549903c5d59edcfa2f3f84126e7b44 AS runtime
RUN groupadd --system review && useradd --system --gid review review \
    && mkdir -p /data/blobs && chown -R review:review /data
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/alembic.ini /app/alembic.ini
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    DOCUMENT_INTELLIGENCE_BLOB_DIR="/data/blobs"
USER review
EXPOSE 8000
CMD ["uvicorn", "--factory", "document_intelligence.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
