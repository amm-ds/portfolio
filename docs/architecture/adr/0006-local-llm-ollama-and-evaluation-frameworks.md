# ADR-0006: Local-first LLM via Ollama; RAGAS + pydantic-evals for evaluation

- **Status:** Accepted
- **Date:** 2026-10-14

## Context 1 — local inference

Project 01 (and the platform generally) needed a default LLM mode that is (a) free to
operate, (b) private by construction, (c) runnable in CI and on a laptop, and (d) good
enough for structured outputs and tool use. The wave-1..9 mock provider satisfied (c)
but contradicted the portfolio's "honest, working" positioning, and cloud keys made (a)
and (b) contingent.

Options considered: **vLLM** (CUDA-centric; Apple Silicon support immature — rejected
for this hardware), **LM Studio** (GUI-first, weaker automation), **MLX** (fast on
Apple Silicon but a separate serving stack), **Ollama** (Metal/llama.cpp performance,
OpenAI-compatible API, native pydantic-ai `OllamaProvider`, headless automation,
model management via one CLI).

Model choice (128 GB MacBook, deliberately medium tier): **qwen3.6:35b-a3b** (MoE, Q4_K_M ≈ 20 GB) as default — Oct-2026
release, ~3.6B active params (fast), strong structured output + tool use; the MLX
runner build was rejected after verification (missing expert weights) in favor of the
llama.cpp quant;
**gpt-oss:20b** (≈ 11 GB) as the documented lighter, agentic-focused alternative;
`OLLAMA_MODEL` switches.

## Decision 1

Local Ollama is the platform's default LLM provider (env-configured OpenAI-compatible
endpoints keep priority when explicitly configured). The runtime mock is removed from
production paths; `FunctionModel` mocks are test-only (`portfolio_core.llm.mock_model_for_tests`).
ADR-0004's fallback-chain section is superseded by this local-first default.

## Context 2 — evaluation frameworks

RAG and agent systems need evaluated quality, not demo impressions. Candidates:
**RAGAS** (RAG-specific: faithfulness, answer relevancy, context precision/recall;
LLM-as-judge; the 2026 standard for product RAG evaluation), **HELM** (broad research
benchmark harness — wrong granularity for per-project product eval), **DeepEval**
(strong, pytest-native; heavier framework lock-in; RAGAS's metric set maps 1:1 onto
the metrics this portfolio already reports), **pydantic-evals** (code-first agent
evaluation from the pydantic-ai ecosystem — installed, integrates with the agent stack).

## Decision 2

- **RAGAS** for RAG evaluation (Project 01; local model as judge → $0 eval cost).
- **pydantic-evals** for agent/workflow evaluation (Project 09).
- HELM/DeepEval consciously not adopted; reasons recorded here.

## Consequences

- Evaluating projects locally requires Ollama running (release-time verification, per
  ADR-0003; CI uses offline stubs and the keyword-judge fallback).
- Cost runbooks reframe: "cost incident" becomes an availability/SLO matter locally;
  cloud endpoints (env-configured) retain cost telemetry.
- New projects inherit the local-first factory via `portfolio_core.llm`.

## Amendment (wave 15, 2026-10-17) — hosted provider A/B on project 01

The local-first default stands; the wave-15 golden-set pass on project 01 adds the
hosted leg of the A/B. The Kimi Code membership endpoint
(`https://api.kimi.com/coding/v1`, model `kimi-for-coding`, OpenAI-compatible) is
wired via `.env`, and the whole evaluation (agent, rubric judge, verify verdicts +
repairs, RAGAS) runs against it with every LLM phase metered through
`portfolio_core.llm_budget` under a hard USD cap per run
(`LLM_COST_LIMIT_USD`). Two endpoint constraints are now platform facts: sampling is
fixed server-side — explicit `temperature` is rejected, so the
`hosted_model_settings()`/`neutralize_hosted_model_settings()` preset omits it
(including neutralizing RAGAS's per-call temperature mutation); thinking CAN be
disabled via `extra_body={"thinking": {"type": "disabled"}}`, which the preset sets.
All reported costs are labelled cloud-equivalent estimates at the public
kimi-k2.8 reference card — the membership key is quota-based, so nothing reported is
a billed amount. The full 65-question pass metered $3.58 (agent $1.79 / RAGAS
$1.13 / verify $0.47 / judge $0.19; 79.6% of input tokens prompt-cache reads); a
first pass tripped the $3.00 cap mid-run and the CLI stopped cleanly — the cap is
enforced, not advisory.
