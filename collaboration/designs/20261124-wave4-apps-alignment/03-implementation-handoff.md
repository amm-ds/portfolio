# Implementation handoff: Wave 4 — Apps Alignment (`agent-chat` & `document-intelligence`)

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution (zero hosted LLM calls)
Branch: `phase0-infra-2026-11-22`
Source design: `collaboration/designs/20261123-portfolio-release-roadmap/01-master-plan.md`

## Objective

Align `apps/agent-chat` and `apps/document-intelligence` across code/config structure, infrastructure hygiene, READMEs, and showcase web articles (`AgentChatArticle.tsx`, `DocumentIntelligenceArticle.tsx`, `apps.ts`) so both flagship app templates share identical quality, terminology, and editorial standards.

## Affected surfaces

- `apps/agent-chat/` (`README.md`, `pyproject.toml`, `.env.example`, `infra/`, `specs/`)
- `apps/document-intelligence/` (`README.md`, `pyproject.toml`, `.env.example`, `infra/`, `specs/`)
- `apps/showcase-web/src/pages/AgentChatArticle.tsx`
- `apps/showcase-web/src/pages/DocumentIntelligenceArticle.tsx`
- `apps/showcase-web/src/lib/apps.ts`
- `collaboration/reviews/20261124-wave4-apps/00-closeout.md` (new)

## Ordered implementation steps

1. **Structural & Infra Audit (`apps/agent-chat` vs `apps/document-intelligence`):**
   - Compare `pyproject.toml` (tool/ruff/mypy/pytest settings), `.env.example`, `infra/` (`Dockerfile` / `docker-compose.yml`), and `README.md` skeletons across both apps.
   - Align any structural inconsistencies (e.g., missing `## Common errors` table or inconsistent reproduce/gate commands in either app's `README.md`, inconsistent `.env.example` comments, or test/lint script gaps) while preserving each app's domain-specific runtime behavior.
2. **Showcase Articles & `apps.ts` Alignment:**
   - Read `apps/showcase-web/src/pages/AgentChatArticle.tsx`, `DocumentIntelligenceArticle.tsx`, and `apps/showcase-web/src/lib/apps.ts`.
   - Align section structure, prose clarity, terminology (linking key concepts to `/glossary#...` where valid in `glossary.json`), and tone across both articles so they read as a cohesive pair without duplicating boilerplate or breaking any existing tests/anchors.
   - Verify no em-dash clause joining or unverified numbers are introduced; every number in both articles must trace to committed eval/metrics artifacts in `apps/agent-chat/reports/` or `apps/document-intelligence/reports/`.
3. **Gates & Close-out:**
   - Run `apps/agent-chat` gates from `apps/agent-chat`: `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest -q`.
   - Run `apps/document-intelligence` gates from `apps/document-intelligence`: `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest -q`.
   - Run `apps/showcase-web` gates: `npm test && npm run lint && npm run build`.
   - Run repo `uv run python scripts/check_docs.py`.
   - Write `collaboration/reviews/20261124-wave4-apps/00-closeout.md`. Do NOT commit or push.
