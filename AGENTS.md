# AGENTS.md

Portfolio + freelancing site: 11 reproducible ML/AI/data case studies under
`projects/`, a FastAPI showcase (`apps/showcase-api`), a React/TypeScript web
app (`apps/showcase-web`), shared libraries (`libs/`), and mkdocs site
(`docs/`). Public repository — every claim must be reproducible from
committed artifacts; never fabricate numbers, clients or outcomes.

## Layout

- `projects/NN-*/` — one experiment each: `portfolio.yaml` (registry card),
  `story.yaml` (case-study article), `src/`, `tests/`, `reports/` (committed
  metrics/figures), `dvc.yaml` pipeline. Python, uv workspace members.
- `libs/portfolio-core` — manifest, story schema, demo registry. `mypy strict`.
- `apps/showcase-api` — FastAPI; serves `/projects`, `/demos`, stories,
  figures, live demo endpoints, `POST /contact/unlock`.
- `apps/showcase-web` — Vite + React + TypeScript. Terminal-like design
  system in `src/styles.css`; shared components in `src/components/`.
- `scripts/` — repo gates and generators (registry, story short copy, route
  manifest, demo contract, story language lint, README figures).

## Gates (run what your change touches)

```bash
uv sync --all-packages --dev          # after dependency changes
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run pytest -q                      # or the affected suites
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
uv run python scripts/lint_story_language.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict          # after docs edits
```

Dev servers: API `uv run uvicorn showcase_api.main:app --port 8000`
(set `CONTACT_PHONE` to enable the phone unlock endpoint); web
`npm run dev` (port 4321, proxies `/projects`, `/demos`, `/rag`, `/health`,
`/contact/unlock` to the API). The API enumerates projects at startup —
restart it after adding a project.

## Conventions

- Experiments follow the 8-section story contract (background, targets, data,
  eda, training, evaluation, results, conclusions); `short_version` in
  `story.yaml` is the single source for card/README/docs copy (≤280 chars).
- Cards on `/projects` take their text from `apps/showcase-web/src/lib/cardCopy.ts`.
- Numbers in copy must exist in the project's committed `reports/metrics.json`.
- Commits: imperative summary + body; one logical change per commit.

## Code quality

All non-trivial work follows `docs/engineering/code-quality-guidelines.md`
(ponytail smallest-complete-change ladder, thermo-nuclear structural review,
pstack working principles), with the vendored skills under
`docs/engineering/skills/`.
