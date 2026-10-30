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

## Amendment (2026-10-14, ADR-0006)

The deterministic mock mode is **removed from production paths** (test-only via
`portfolio_core.llm.mock_model_for_tests`), and the default provider chain is:
env-configured OpenAI-compatible endpoint → **local Ollama** (default model
per ADR-0006: `qwen3.6:35b-a3b-q4_K_M`, `OLLAMA_MODEL` overrides).
See ADR-0006.

## Consequences

- Zero secrets in CI; eval harness runs against the mock with fixed expectations
  and against the real provider in release runs (results documented per release).
- Cost/latency SLOs are measured identically across providers; runbook
  `llm-cost-incident.md` documents provider/Ollama operation, budget guards,
  and the public RAG kill switch. Runtime mocks and retrieval-only fallback are
  not production modes.
