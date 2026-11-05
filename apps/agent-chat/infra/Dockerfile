# syntax=docker/dockerfile:1
# Multi-stage build for the agent-chat API. The base image intentionally
# excludes the [embeddings] extra (torch is ~GBs); the compose stack runs the
# hashing embedder. For MiniLM in the image, add `--extra embeddings` to the
# second `uv sync` and set AGENT_CHAT_EMBEDDER=minilm.

FROM ghcr.io/astral-sh/uv:0.5.31-python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
RUN uv sync --locked --no-dev

FROM python:3.12.9-slim AS runtime
RUN groupadd --system agent && useradd --system --gid agent agent
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    AGENT_CHAT_DATABASE_URL="postgresql+asyncpg://agent_chat:agent_chat@db:5432/agent_chat" \
    AGENT_CHAT_EMBEDDER="hashing"

USER agent
EXPOSE 8000
CMD ["uvicorn", "--factory", "agent_chat.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
