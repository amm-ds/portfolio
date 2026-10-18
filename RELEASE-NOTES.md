# Release notes — v1.0.0

First public release of the amm-ds portfolio. Factual changelog; for the underlying
evidence see the linked audits.

## Projects — 10 case studies, real data on the primary track

Each of the 10 projects (`projects/01-rag-agent` … `projects/10-uplift-experimentation`) ships a design
record, a reproducible DVC pipeline, and an evaluation harness. Where a dataset has a
real, versioned source (DVC registry under `registry/`), the primary track runs against
that real data; synthetic/fallback data exists only where licensing or size prevents
redistribution, and each case study states which track its reported metrics come from.

## Serving endpoints and contracts — 4

Four projects expose live serving endpoints through the showcase API
(`apps/showcase-api`): demand forecasting (02, 05 churn scoring, 06 routing
optimization solve, 07 mobility zone forecast). Every endpoint is backed by a pydantic request/response
contract; contracts are the API boundary per ADR-0002 and are tested in CI.

## Hosted-Kimi integration with enforced budget caps

The LLM provider abstraction (ADR-0004) supports a hosted-Kimi route alongside the
local model. Budget caps are enforced in code — per-request and aggregate token/cost
limits with fail-closed behavior when the cap would be exceeded — not merely
documented. The public deployment runs the local-model route; the hosted route is
env-gated (see the LLM cost-incident runbook, `docs/runbooks/llm-cost-incident.md`).

## Deployment pack

- `docker-compose.yml`: one-command local bring-up of API + web
  (`make docker-up` → http://localhost:8000).
- `deploy/docker-compose.prod.yml` + `deploy/Caddyfile`: production compose with a
  hardened Caddy reverse proxy (security headers, confined static file serving —
  path-traversal fix from audit A-1 verified by PoC re-run).
- `deploy/DEPLOY.md`: operator runbook.

## Reproducibility

All pipeline code, configs, and small artifacts are committed to git; large datasets
are versioned via DVC with the registry remotes documented per dataset. A clean clone
plus `dvc pull` reproduces every reported metric; CI re-runs the test suite and the
docs build on every push.

## Audits

- Pre-publish review, 2026-10-14 — `docs/audits/pre-publish-2026-10-14.md`
- Productization gap report — `docs/audits/productization-gap-report.md`
- External audit response, 2026-10-15 — `docs/audits/2026-10-15-external-audit-response.md`
