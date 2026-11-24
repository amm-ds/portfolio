# Close-out: Wave 5 — Backend Deploy Readiness & Public Repo Hygiene

Date: 2026-11-24
Executor: Kimi Code
Branch: `phase0-infra-2026-11-22` (not committed; Claude reviews, validates, commits, merges to `main`, pushes)
Handoff: `collaboration/designs/20261124-wave5-backend-and-hygiene/03-implementation-handoff.md`

Zero hosted LLM calls were made. All verification ran offline against committed
artifacts and deterministic fixtures.

## Part 1 — Backend & deploy readiness audit

Audited `apps/showcase-api/src/showcase_api/` (`main.py` — 1,224 lines,
`contact.py`, `live.py`, `middleware.py`, `vitals.py`, `spa.py`,
`spa_heads.py`) and `deploy/` (`DEPLOY.md`, `Caddyfile`,
`docker-compose.prod.yml`, plus `HETZNER.md`, `MAINTENANCE.md`,
`DEPLOYMENT-REPORT.md`).

**Finding: one real doc/deploy mismatch, fixed.**

- `deploy/DEPLOY.md` documented `DAILY_LIVE_BUDGET` default `1000` in two
  places, but `deploy/docker-compose.prod.yml` deliberately pins
  `${DAILY_LIVE_BUDGET:-10}` (compose default introduced in `b60ad3b1`, kept
  through the `db4fc139` int-parse fix). In the supported topology the
  effective production default is therefore 10, not 1000. DEPLOY.md now says
  `10` in prod compose (application fallback `1000`) in both the
  configuration table and the kill-switch/budget section, and notes the
  compose default is deliberately conservative. `HETZNER.md`'s historical
  incident record (`db4fc13`) needs no change.

**No other changes.** The audit confirmed the deployment contract holds:

- Fail-closed surfaces: `/docs`/`/redoc`/`/openapi.json` register only with
  `ENABLE_API_DOCS=1`; `/rag/chat` only with `RAG_CHAT_ENABLED=1` and the
  production image omits the rag_agent package and index; `POST /contact/unlock`
  fails closed with 503 when `CONTACT_PHONE` is unset; live POSTs are behind
  `LiveGuard` (kill switch + `/tmp/live_disabled` + per-UTC-day budget).
- `POST /contact/unlock`: validation, per-deployment phone from env,
  successful-unlock-only JSONL store, 30-day/1,000-entry retention, atomic
  rewrites, inter-process flock, operator deletion without an HTTP route.
- Middleware: per-IP POST token bucket (bounded store), 1 MB body cap with
  replay, request IDs, salted IP hashing with a one-time warning when
  `IP_HASH_SALT` is unset (production compose requires it via `:?`).
- SPA serving: path-traversal-confined, immutable caching only for
  content-hashed assets, HEAD support, manifest-backed route matching with a
  derivation fallback, per-route `<head>`/`<noscript>` rendering with
  fail-soft warnings, JSON-LD Person block.
- `Caddyfile`: required ACME email, HSTS without preload (conscious opt-out),
  strict SPA CSP with route-scoped report/figure exceptions, 301 canonicals,
  single published service; `docker-compose.prod.yml`: digest-pinned Caddy,
  read-only rootfs, no capabilities, tmpfs `/tmp`, healthchecks, resource
  limits, log rotation, required (`:?`) DOMAIN/ACME_EMAIL/IP_HASH_SALT.

## Part 2 — Public repository hygiene

Removed development-exclusive documents (all named in the handoff):

- `docs/audits/` (7 files: pre-publish review, productization gap report,
  external audit response, portfolio website evaluation, full-repo review,
  two 2026-11 production assessments)
- `docs/portfolio_audit_amm-ds.md`
- `docs/repository_setup_report_senior_data_scientist.md`
- `docs/engineering/production-review-2026-11-06.md`

`RELEASE-NOTES.md` is public-facing release copy, not internal; kept, with
its three dead `docs/audits/` links replaced by a note that pre-release audit
records are retained in git history rather than shipped in `docs/`.

Reference updates so nothing dangles:

- `mkdocs.yml`: removed the three `audits/` nav entries from Engineering and
  deleted the `exclude_docs:` block (its two files no longer exist).
- `docs/llms.txt`: dropped the audits line from the engineering record and
  the "(ADRs, audits)" Diátaxis note; added the statistical-intervals entry.
- Verified by repo-wide grep that no remaining first-party file links to the
  deleted paths; the only mentions left are internal records
  (`collaboration/`, `artifacts/`) that intentionally cite history.

Kept visitor-focused per the handoff: `README.md`, `llms.txt`,
`docs/llms.txt`, `docs/index.md`, `docs/projects/`, `docs/data-registry/`,
`docs/architecture/`, `docs/engineering/{repo-conventions,
code-quality-guidelines,statistical-intervals}.md`, `deploy/` (plus
`docs/runbooks/`, `docs/site/`, and the engineering playbook, which are
visitor-relevant). `collaboration/ITERATION_TRACKER.md` and active
`collaboration/` records untouched apart from this closeout.

## Gate repair

`uv run ruff format --check .` failed on a pre-existing violation in
`collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/02-architecture-proposal.md`
(an unstably-split fenced Python signature — ruff wants it collapsed).
Formatting-only fix via `uv run ruff format` on that file (4 lines → 1
collapsed signature); no content change.

## Gates (all from the handoff, run from repo root)

| gate | result |
|---|---|
| `ruff check .` | pass (All checks passed!) |
| `ruff format --check .` | pass (after the design-doc format fix) |
| `mypy libs apps/showcase-api` | pass (29 source files, no issues) |
| `pytest apps/showcase-api -q` | pass (102 passed) |
| `scripts/check_docs.py` | pass (`check-docs: OK`) |
| `scripts/check_short_copy.py --check` | pass |
| `scripts/check_headline_numbers.py` | pass (11 claims checked, 0 findings) |
| `scripts/check_demo_contract.py` | pass (both demos + static registry current) |
| `scripts/lint_story_language.py` | pass (13 stories, 0 errors, 1 pre-existing soft-budget warning on 01-rag-agent evaluation — present with the changes stashed) |
| `mkdocs build --strict` | pass |
| `apps/showcase-web`: `npm test`, `npm run lint`, `npm run build` | pass (run during Wave 4; no web changes since) |

## Files touched (working tree only; nothing committed)

- M `deploy/DEPLOY.md`
- M `mkdocs.yml`
- M `docs/llms.txt`
- M `RELEASE-NOTES.md`
- M `collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/02-architecture-proposal.md` (formatting only)
- D `docs/audits/` (7 files), `docs/portfolio_audit_amm-ds.md`,
  `docs/repository_setup_report_senior_data_scientist.md`,
  `docs/engineering/production-review-2026-11-06.md`
- (Wave 4 files remain modified in the same working tree — see
  `collaboration/reviews/20261124-wave4-apps/00-closeout.md`)

## Notes for review

- Endpoint regression check: the API suite (102 tests) covers
  `/health`, `/ready`, `/projects`, `/demos`, `POST /contact/unlock` (valid,
  invalid, unconfigured-phone 503, retention), live-guard 503s, rate limiting,
  SPA heads/catch-all, and vitals validation.
- A stale `.coverage` file and `__pycache__` under `apps/showcase-api/` are
  gitignored working artifacts; no action needed.
- The other agent session's `02-demand-forecasting` M5 selection shards were
  left running throughout (owner chose not to answer the stop question);
  they do not touch any file in this wave.
