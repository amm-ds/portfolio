# Runbook — LLM cost / latency incident (Project 01)

**SLOs (see `projects/01-rag-agent/DESIGN.md`):** p95 end-to-end latency and
cost-per-query budgets are documented per release. Breaching either for 15
minutes = incident.

## Fallback chain

1. **Primary:** configured OpenAI-compatible provider (env-configured base URL).
2. **Degraded:** smaller context budget — fewer retrieved chunks, shorter
   history; answer quality drops but the service stays up.
3. **Emergency:** mock/local mode — retrieval-only answers with citations;
   clearly labeled as degraded in the UI and logs.

Switching modes is a config change (`LLM_MODEL`, context-size params), not a
deploy.

## Cost controls

- Hard per-request token budgets in `RunConfig` (validated by pydantic).
- Caching: query-embedding cache and response cache keyed by
  (query, index-version, model) in `data/cache/` (DVC-ignored, gitignored).
- Batch eval runs report tokens/cost per run; a 2× week-over-week increase
  triggers review even inside budget.

## Diagnose

- pydantic-ai emits OpenTelemetry-compatible spans; correlate latency by stage
  (retrieve → rerank → generate).
- p95 decomposition tells you which stage to budget first — almost always
  generation, almost never retrieval.
