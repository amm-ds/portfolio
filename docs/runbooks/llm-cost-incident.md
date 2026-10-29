# Runbook — LLM cost / latency incident (Project 01)

**SLOs (see `projects/01-rag-agent/DESIGN.md`):** p95 end-to-end latency and
cost-per-query budgets are documented per release. Breaching either for 15
minutes = incident.

## Fallback chain

1. **Primary:** configured OpenAI-compatible provider (env-configured base URL),
   or local Ollama when no hosted provider is configured.
2. **Degraded:** smaller context budget — fewer retrieved chunks, shorter
   history; answer quality drops but the service stays up.
3. **Emergency:** disable the public RAG kill switch. Set `RAG_CHAT_ENABLED`
   empty and recreate the API container; the routes are then absent. There is
   no production mock or retrieval-only fallback.

Provider/model changes and the showcase kill switch require a process restart;
runtime environment is read once. See `deploy/DEPLOY.md` for the exact recreate
command and budget variables.

## Cost controls

- Hard per-request token budgets in `RunConfig` (validated by pydantic), plus
  per-process `LLM_COST_LIMIT_USD`, `LLM_MAX_REQUESTS`, and
  `LLM_TOTAL_TOKENS_LIMIT` guards. Cost caps are cloud-equivalent estimates,
  not provider-side billing limits.
- There is no application query-embedding or RAG-response cache. Hosted
  provider prompt-cache usage is metered when the provider returns it; showcase
  artifact/ETag caching is documented separately in `apps/showcase-api/SERVING.md`.
- Batch eval runs report tokens/cost per run; a 2× week-over-week increase
  triggers review even inside budget.

## Diagnose

- pydantic-ai emits OpenTelemetry-compatible spans; correlate latency by stage
  (retrieve → rerank → generate).
- p95 decomposition tells you which stage to budget first — almost always
  generation, almost never retrieval.
