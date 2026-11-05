# Welcome to agent-chat

This document exists so the one-shot ingest service has something to index
out of the box (`docker compose run --rm ingest`). Replace it with your own
knowledge base — markdown and txt files under `docs/`.

## What the template gives you

A pydantic-ai v2 agent with typed tools (calculator, clock, opt-in fetch),
disk-loaded skills with progressive disclosure (handbook, summarize), RAG
over pgvector, human approval for consequential actions, structured answers
with citations, and a FastAPI surface that streams every step as typed SSE
events.
