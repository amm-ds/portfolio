# Repository Conventions

The rules every change follows. Agent-facing quick reference lives in the root
`AGENTS.md`; quality-review rules live in
[code-quality-guidelines.md](code-quality-guidelines.md).

## Story contract

Every experiment's `story.yaml` carries eight sections in a fixed order:
`background, objectives, data, eda, training, evaluation, results,
conclusions`. Renderer behavior depends on the ids — keep them stable.

- `short_version` (≤280 chars) is the single plain-text source for the
  project card, README rows, docs openings, and social text. Never restate
  its numbers by hand — run
  `uv run python scripts/gen_story_short.py` and let
  `scripts/check_short_copy.py --check` prove the surfaces match.
- Roadmaps are finalized: `status: delivered` milestones only, 4–7 items.
- `key_concepts` render as a card in Background; `figure_captions` (≤3
  figures per section) render as figure footers.
- Every `data` section links its dataset card, e.g.
  `https://amm-ds.github.io/portfolio/data-registry/nyc-tlc/`.

## Truth in copy

- Numbers in any copy surface must exist in the project's committed
  `reports/metrics.json` (or another committed artifact). If a number cannot
  be traced to a committed file, it does not ship.
- Present last results only: development history belongs in DESIGN.md
  changelogs and revision notes, not in public prose. No fabricated clients,
  outcomes, or capabilities — the repository is public.
- Terminology: metric names define themselves at first use or link the
  glossary; round for people (95%, not 0.9460) and keep full precision in
  tables.

## Site copy surfaces

- `/projects` card bodies come from `apps/showcase-web/src/lib/cardCopy.ts`
  (`CARD_DOES` / `CARD_ACHIEVES` / `CARD_TAGS`) — not from story text.
- Generated registries (`staticRegistry.ts`, `storyShort.ts`,
  `route-manifest.json`, sitemap) are rebuilt with their scripts; never edit
  by hand. Check with each script's `--check` mode in CI.
- New datasets are registered twice: a `registry/*.dvc` manifest
  (`dvc import-url --no-exec`) and a human-readable card in
  `docs/data-registry/` linked from `registry/README.md` and
  `docs/data-registry/index.md`.

## Commits

Imperative summary + body; one logical change per commit. Agents do not run
git — the session owner commits.

## Environment notes

- Python: one uv workspace; `uv sync --all-packages --dev` after dependency
  changes; lockfile committed.
- DVC: pipeline outs (data, reports) are tracked by DVC, not git. `dvc repro`
  from a project directory; `dvc update registry/` refreshes source metadata.
- The showcase API enumerates projects at startup — restart it after adding
  or renaming a project.
