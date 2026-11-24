# Implementation handoff: Wave 5 — Backend Deploy Readiness & Public Repo Hygiene

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution (zero hosted LLM calls)
Branch: `phase0-infra-2026-11-22`
Source design: `collaboration/designs/20261123-portfolio-release-roadmap/01-master-plan.md`

## Objective

1. **Backend & Deploy Readiness (`apps/showcase-api/`, `deploy/`, `Dockerfile`):**
   - Audit `apps/showcase-api/src/showcase_api/` (`main.py`, `contact.py`, `live.py`, `middleware.py`, `vitals.py`, `spa.py`, `spa_heads.py`) and `deploy/` (`DEPLOY.md`, `Caddyfile`, `docker-compose.prod.yml`, `HETZNER.md`, `MAINTENANCE.md`) for deployment readiness.
   - Ensure `apps/showcase-api` tests, `ruff`, and `mypy` pass cleanly, and that `/health`, `/ready`, `POST /contact/unlock`, and `/projects` / `/demos` endpoints have no regressions.
2. **Public Repository Hygiene (Remove/Declutter Development-Exclusive Docs):**
   - Since the repository is public, audit and clean up stale development-exclusive documents (e.g., `docs/audits/`, `docs/portfolio_audit_amm-ds.md`, `docs/repository_setup_report_senior_data_scientist.md`, `docs/engineering/production-review-2026-11-06.md`, `RELEASE-NOTES.md` if internal, and any redundant dev-only scratch) — either removing stale internal audits or moving/updating `mkdocs.yml` nav and `docs/` links so `check_docs.py` and `uv run mkdocs build --strict` pass with 0 broken links.
   - Keep `README.md`, `llms.txt`, `docs/llms.txt`, `docs/index.md`, `docs/projects/`, `docs/data-registry/`, `docs/architecture/`, `docs/engineering/{repo-conventions,code-quality-guidelines,statistical-intervals}.md`, and `deploy/` crisp and visitor-focused.
   - Keep `collaboration/ITERATION_TRACKER.md` and active `collaboration/` records clean without leaving untracked clutter.

## Affected surfaces

- `apps/showcase-api/` (audit + tests/fixes if any issue is found)
- `deploy/` (`DEPLOY.md`, `DEPLOYMENT-REPORT.md` if doc links need updating)
- `docs/` and `mkdocs.yml` (declutter dev-exclusive audits/setup reports; update nav/links)
- `collaboration/reviews/20261124-wave5-backend-and-hygiene/00-closeout.md` (new)

## Gates & Close-out

Run from repo root:
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy libs apps/showcase-api
uv run pytest apps/showcase-api -q
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_demo_contract.py
uv run python scripts/lint_story_language.py
uv run mkdocs build --strict
cd apps/showcase-web && npm test && npm run lint && npm run build
```

Write `collaboration/reviews/20261124-wave5-backend-and-hygiene/00-closeout.md`. Do NOT commit or push; Claude will review, validate, commit, merge to `main`, and push to trigger the website deployment.
