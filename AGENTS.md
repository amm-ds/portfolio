# AGENTS.md

Portfolio + freelancing site: reproducible ML/AI/data case studies under
`projects/`, a FastAPI showcase (`apps/showcase-api`), a React/TypeScript web
app (`apps/showcase-web`), shared libraries (`libs/`), and an mkdocs site
(`docs/`). Public repository — every claim must trace to a committed artifact.

## Layout

- `projects/NN-*/` — one experiment each: `portfolio.yaml` (registry card),
  `story.yaml` (case-study article), `src/`, `tests/`, `reports/` (committed
  metrics/figures), `dvc.yaml` pipeline. Python, uv workspace members.
- `libs/portfolio-core` — manifest, story schema, demo registry. `mypy strict`.
- `apps/showcase-api` — FastAPI; serves `/projects`, `/demos`, stories,
  figures, live demo endpoints, `POST /contact/unlock`.
- `apps/showcase-web` — Vite + React + TypeScript; terminal-like design
  system in `src/styles.css`; shared components in `src/components/`.
- `apps/agent-chat` — independent uv workspace: Pydantic AI agent, FastAPI
  backend, React chat UI, Postgres/pgvector, browser-session memory, typed
  evals, specs, and clean demo media. Run its gates from `apps/agent-chat`.
- `apps/document-intelligence` — independent uv workspace: page-level PDF
  analysis workbench — one AI call per page produces cited summaries, typed
  entities, and topics, plus page-scoped cited chat with bounded history; exact
  parser-resolved evidence, leased worker, Postgres records, React workbench,
  fixtures, and page-level offline/live eval. Run its backend and `web/` gates
  from this directory.
- `scripts/` — repo gates and generators (registry, story short copy, route
  manifest, demo contract, story language lint, README figures).
- `registry/` + `docs/data-registry/` — dataset manifests and cards.
- `collaboration/` — dual-agent workspace: Claude Code owns design and review,
  Kimi Code owns execution. Use `make collab` to launch both side by side.

## Claude ↔ Kimi role split

Claude Code produces design briefs, architecture proposals, implementation
handoffs, and review responses under `collaboration/`. Kimi Code implements only
from an approved handoff, runs the touched gates, and reports exact files and
verification results. Agents do not mutate git unless the session owner
explicitly asks.

## Gates (run what your change touches)

```bash
uv sync --all-packages --dev          # after dependency changes
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run pytest -q                      # or the affected suites
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict          # after docs edits
```

Dev servers: API `uv run uvicorn showcase_api.main:app --port 8000`
(set `CONTACT_PHONE` to enable the phone unlock endpoint); web `npm run dev`
(port 4321, proxies `/projects`, `/demos`, `/rag`, `/health`,
`/contact/unlock` to the API). The API enumerates projects at startup —
restart it after adding a project.

Note for macOS arm64 hosts: the Node here is arm64 (`node -p process.arch`).
If `npm ci` was last run under Rosetta/x64, Vite fails with "Cannot find
module @rollup/rollup-darwin-arm64" (npm optional-dependencies bug). Fix with
`npm ci` under the arm64 node, or `npm i --no-save @rollup/rollup-darwin-arm64`.
The `web-dev` compose service avoids the issue entirely: it installs
node_modules inside the container and mounts an anonymous `/web/node_modules`
volume so the host tree never shadows the image's.

## Rules of the house

- Conventions (story contract, truth-in-copy, copy surfaces, commits,
  environment): `docs/engineering/repo-conventions.md`.
- Code quality (smallest complete change, thermo-nuclear review bar, pstack
  principles): `docs/engineering/code-quality-guidelines.md`, with the
  vendored skills under `docs/engineering/skills/`.
- Deployment options and the cutover checklist: `deploy/DEPLOYMENT-REPORT.md`.
