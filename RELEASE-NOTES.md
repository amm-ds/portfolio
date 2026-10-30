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
(`apps/showcase-api`): demand forecasting (02), churn scoring (05), routing
optimization solve (06), and mobility zone forecast (07). Every endpoint is
backed by a pydantic request/response contract; contracts are the API
boundary per ADR-0002 and are tested in CI.

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

All pipeline code, configs, and small artifacts are committed to git — reported
metrics, figure specs, and serving bundles ship in the repository, so a clean
clone already shows every headline number and serves a functional app without
`dvc pull`. Bulky raw data stays DVC-tracked and regenerates with `dvc repro`
from the checksum-pinned sources (no cloud remote assumed, per ADR-0003;
import manifests under `registry/` per ADR-0007). CI re-runs the test suite and
the docs build on every push.

## Audits

- Pre-publish review, 2026-10-14 — `docs/audits/pre-publish-2026-10-14.md`
- Productization gap report — `docs/audits/productization-gap-report.md`
- External audit response, 2026-10-15 — `docs/audits/2026-10-15-external-audit-response.md`

## Result updates since first publication (2026-10-29, verified)

Point-in-time corrections; the project pages and `story.yaml` files are the
live source of truth.

- **03 anomaly detection** — NAB detector × feature sweep: no family winner
  (PR-AUC 0.515–0.574); episode dedup + a 24 h per-series page cap cut alerts
  1,609 → 80 while *raising* range-F1 0.157 → 0.315.
- **05 churn** — FN-cost sensitivity re-run: served-isotonic cost 510/601/699
  at t\*=0.200/0.175/0.100 for FN=3/5/8, every paired-bootstrap CI excludes
  zero; calibration's cost edge is itself cost-model dependent (isotonic helps
  at FN=5, slightly hurts at FN=8). Fairness slices are raw-model (t=0.150):
  the raw policy misses 19 of 36 one-year and all 9 two-year churners — the
  served artifact is isotonic at t=0.175.
- **06 routing** — fleet-first ALNS variant: −0.07 mean vehicles at +0.07 pp
  gap (vehicles-first ranking restated: ALNS 38/56, fleet-first variant 5/56);
  equal-budget unhinted CP-SAT produced no feasible plan on any of the 56
  instances at 10 s.
- **07 mobility** — green-transfer control: a GBM retrained on two months of
  green history beats green persistence on all three metrics (MAE 0.180 vs
  0.212, RMSE 0.688 vs 1.100, MAPE 66.4% vs 81.8%) — per-service retraining
  is the measured fix. Drift observatory scored 2024-11 (+8.2%) and 2024-12
  (+7.9%), both in-window; unseen-drift behavior remains unmeasured.
- **09 agentic workflows** — two repeat hosted passes confirmed 15/15 answers
  and exact tool sets with zero unplanned calls (~$0.10–0.15 cloud-equivalent
  per suite); suite cost basis restated at **$0.13 of the $2.00 cap
  (~$0.0088/task)**, cloud-equivalent rather than billed.
