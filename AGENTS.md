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

## Rules of the house

- Conventions (story contract, truth-in-copy, copy surfaces, commits,
  environment): `docs/engineering/repo-conventions.md`.
- Code quality (smallest complete change, thermo-nuclear review bar, pstack
  principles): `docs/engineering/code-quality-guidelines.md`, with the
  vendored skills under `docs/engineering/skills/`.
- Deployment options and the cutover checklist: `deploy/DEPLOYMENT-REPORT.md`.
