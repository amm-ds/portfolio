# ADR-0004: LLM provider abstraction

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Project 01 (RAG agent) must run in CI without secrets, offline for demos, and
against a real provider when a key exists. Hard-wiring one SDK would break at
least one of those, and would age poorly as providers change.

## Decision

A single factory — `portfolio_core.llm.build_model()` — built on pydantic-ai's
provider wrappers:

1. **Configured provider:** if `LLM_BASE_URL` + `LLM_API_KEY` are set, an
   OpenAI-compatible provider is constructed against that base URL
   (e.g. Kimi/Moonshot at `https://api.moonshot.ai/v1`). Anthropic-compatible
   endpoints are reachable the same way without new code.
2. **Mock provider:** deterministic, citation-aware canned responses when no key
   is configured (CI, offline). Same `output_type` contracts enforced.
3. **TestModel/FunctionModel:** unit tests inject scripted models via pydantic-ai
   — no network, no flakiness.

Projects never import an LLM SDK directly; they depend on the factory and the
pydantic output models.

## Consequences

- Zero secrets in CI; eval harness runs against the mock with fixed expectations
  and against the real provider in release runs (results documented per release).
- Cost/latency SLOs are measured identically across providers; runbook
  `llm-cost-incident.md` documents the fallback chain (provider → local mock
  with degraded retrieval-only answers).
