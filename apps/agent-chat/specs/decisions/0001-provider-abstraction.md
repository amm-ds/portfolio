# ADR-0001: Model provider abstraction (Ollama default, hosted, fallback)

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

The template is lifted out and adapted by teams with different deployment
realities: no secrets and no budget (local Ollama), an existing hosted
OpenAI-compatible contract, or both (local first, hosted when the local box is
down). Hard-wiring one SDK into the agent would force every adopter to edit
agent code and would age poorly as providers change. CI and tests add a third
requirement: determinism with no network and no keys.

## Decision

A single factory — `agent_chat.models.build_model(settings)` — is the only
file that knows how to reach a model:

1. **Ollama (default).** `AGENT_CHAT_PROVIDER=ollama` talks to a local Ollama
   at `AGENT_CHAT_OLLAMA_BASE_URL` (default `http://localhost:11434`), model
   `qwen3:8b`. Ollama exposes an OpenAI-compatible endpoint, so the same
   client shape serves both branches.
2. **Hosted OpenAI-compatible.** `AGENT_CHAT_PROVIDER=hosted` points an
   `OpenAIChatModel` at `AGENT_CHAT_HOSTED_BASE_URL` /
   `AGENT_CHAT_HOSTED_API_KEY` / `AGENT_CHAT_HOSTED_MODEL`. Any
   OpenAI-compatible endpoint (vLLM, LiteLLM, a cloud provider) works without
   new code.
3. **Fallback chain.** A non-empty `*_FALLBACK_MODEL` composes the primary and
   fallback into pydantic-ai's `FallbackModel`, which fails over **only on
   provider API errors** — a content-level failure is the model answering, not
   the provider being down, and must surface to the caller.

Tests never come through the factory: they inject a scripted
`FunctionModel` (`agent_chat.testing`), so suites run offline and assertions
pin what the model "saw".

## Consequences

- Swapping providers is a configuration change, or at most an edit confined to
  `models.py`; the agent, tools, and API never know.
- One client shape (OpenAI-compatible) covers the default and hosted branches;
  adding a genuinely different SDK (e.g. Anthropic-native) means one new
  branch here, not a rewrite.
- Failover semantics are explicit: outages, not bad answers, trigger the
  fallback. Adopters who want retry-on-content behavior configure
  `AGENT_CHAT_MODEL_RETRIES`, which pydantic-ai applies to output validation.
