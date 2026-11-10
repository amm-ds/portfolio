# Architecture decision records

Every platform-level choice carries an ADR (context → options → decision →
consequences). The platform ADRs live here; the lift-out-able agent-chat
template keeps its own decision records under
`apps/agent-chat/specs/decisions/` (linked cross-repo below). Platform ADR
0006 amends part of ADR-0004, and agent-chat ADR-0006 amends ADR-0005.

## Platform ADRs

| ADR | Decision (one line) | Status |
|---|---|---|
| [0001 — uv workspace monorepo](0001-uv-workspace-monorepo.md) | One uv workspace at the repository root (`libs/*`, `projects/*`, `apps/*`); heavy dependencies (torch, faiss) declared only by the projects that need them. | Accepted |
| [0002 — pydantic contracts at every boundary](0002-pydantic-contracts-everywhere.md) | Dataset records, run configs, API requests/responses are typed models — drift and config typos fail loudly at the boundary, not downstream. | Accepted |
| [0003 — DVC pipelines for reproducibility](0003-dvc-pipeline-reproducibility.md) | Per-project DVC stages (`prepare → … → evaluate`) make "reproducible" testable: a stranger reproduces headline results from a clean clone. | Accepted |
| [0004 — LLM provider abstraction](0004-llm-provider-abstraction.md) | One factory — `portfolio_core.llm.build_model()` on pydantic-ai — runs CI without secrets, offline on local Ollama, or against any OpenAI-compatible endpoint. | Accepted |
| [0005 — plotly as the only visualization library](0005-plotly-as-only-viz.md) | All figures go through `portfolio_core.plotting` (shared theme, one export path) so READMEs, the mkdocs site, and the React app render identical charts. | Accepted; rendering side amended by ADR-0008 |
| [0006 — local-first LLM + evaluation frameworks](0006-local-llm-ollama-and-evaluation-frameworks.md) | Ollama is the default model runtime (free, private, CI-runnable); RAGAS + pydantic-evals grade LLM quality with committed numbers. | Accepted |
| [0007 — DVC beyond pipelines](0007-dvc-metrics-experiments-registry.md) | `reports/metrics.json`, queued HPO experiments, and the dataset registry become declarative DVC concerns instead of ad-hoc scripts and markdown-only cards. | Accepted |
| [0008 — ECharts renderer with plotly fallback](0008-echarts-renderer-plotly-fallback.md) | Committed plotly payloads stay the single figure source; the showcase web converts and renders them with ECharts, per-figure plotly.js fallback when conversion fails. | Accepted; amends ADR-0005 |

## agent-chat template ADRs

The chatbot-agent chassis (see
[Agent Chat](../../apps/chatbot-agent.md)) decides its own lift-out-level
questions in
[`apps/agent-chat/specs/decisions/`](https://github.com/amm-ds/portfolio/tree/main/apps/agent-chat/specs/decisions):

| ADR | Decision (one line) | Status |
|---|---|---|
| [0001 — model provider abstraction](https://github.com/amm-ds/portfolio/blob/main/apps/agent-chat/specs/decisions/0001-provider-abstraction.md) | Ollama by default, hosted OpenAI-compatible as an env switch, an optional fallback chain — the agent code never knows which is active. | Accepted |
| [0002 — Postgres + pgvector for storage and retrieval](https://github.com/amm-ds/portfolio/blob/main/apps/agent-chat/specs/decisions/0002-postgres-pgvector.md) | One database for conversations and retrieval chunks; SQLite covers docker-free dev and CI without a migration framework. | Accepted |
| [0003 — skills as disk folders](https://github.com/amm-ds/portfolio/blob/main/apps/agent-chat/specs/decisions/0003-skills-disk-folders-capabilities.md) | Markdown-authored skill folders with progressive disclosure — adding a playbook is adding a folder, no framework code. | Accepted |
| [0004 — in-band approval gate](https://github.com/amm-ds/portfolio/blob/main/apps/agent-chat/specs/decisions/0004-in-band-approval-gate.md) | Consequential tools ask in-band and default to deny on timeout — no out-of-band channel, no approve-by-default. | Accepted |
| [0005 — Harness-style memory and bounded history](https://github.com/amm-ds/portfolio/blob/main/apps/agent-chat/specs/decisions/0005-memory-harness.md) | On-demand notebook recall plus sliding-window history keeps model context bounded and inspectable. | Accepted; identity amended by ADR-0006 |
| [0006 — anonymous browser-session identity](https://github.com/amm-ds/portfolio/blob/main/apps/agent-chat/specs/decisions/0006-browser-session-identity.md) | A sessionStorage UUID scopes conversations, notebooks, and approvals without account infrastructure. | Accepted; amends ADR-0005 |
