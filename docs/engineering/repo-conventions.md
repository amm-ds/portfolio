# Repository Conventions

The rules every change follows. Agent-facing quick reference lives in the root
`AGENTS.md`; quality-review rules live in
[code-quality-guidelines.md](code-quality-guidelines.md).

## Story contract

Every experiment's `story.yaml` carries eight sections in a fixed order:
`background, objectives, data, eda, training, evaluation, results,
conclusions`. Renderer behavior depends on the ids — keep them stable.

- `short_version` (≤280 chars) is the single plain-text source for the
  project card, README rows, docs openings, and social text. Run
  `uv run python scripts/gen_story_short.py` to regenerate only `storyShort.ts`;
  `scripts/check_short_copy.py --check` verifies the check-only README/docs
  surfaces without writing them.
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

## Metrics storage

- **Headline `reports/metrics.json` belongs in git.** Small, human-diffable
  evidence files (a few KB) must be readable on a fresh CI checkout without
  a `dvc pull`. Any test or check that cites a number must be able to read it
  from the repo directly.
- **Large derived data stays DVC-tracked** (prepared panels, parquet
  payloads, model binaries). DVC-outs are allowed to be absent locally until
  `dvc repro` regenerates them.
- Exceptions: projects 11 and 12 keep their metrics as DVC outs for now —
  checks read those projects' committed `README.md` instead (same printed
  numbers). New projects follow the git-first convention above.

## Documentation

- `llms.txt` at the repository root maps the repo for AI agents (layout,
  entry points, gates, conventions); `docs/llms.txt` maps the published site.
  Keep both under ~120 lines; mkdocs copies `docs/llms.txt` into the build as
  a static file (no wiring needed — verify `site/llms.txt` after
  `uv run mkdocs build --strict` if the layout changes).
- `scripts/check_docs.py` is the docs gate: relative markdown links must
  resolve to a file/heading anchor on first-party Markdown surfaces, except
  that git-ignored DVC outputs may be absent until their pipeline regenerates
  them. Fenced code blocks need a language tag, and `/glossary#slug` anchors
  referenced from `apps/showcase-web/src` must exist in `glossary.json`. It
  runs in CI (gate job) and through `uv run python scripts/lint_ci.py`; fix
  what it finds, do not relax it.
- Documentation has three distinct jobs: README is the current operational and
  evidence snapshot, `story.yaml` is the case study, and DESIGN.md holds history
  and alternatives. Use short openings, put reproduction near the top, keep one
  idea per paragraph, and write active, present-tense, evidence-led prose.
  Metrics include units, baseline, and split. Remove wave/changelog prose from
  public READMEs and preserve useful history in DESIGN.md changelogs.
- Avoid em-dash clause joining by default, not dashes themselves. Preserve
  numeric ranges, math, arrows, YAML front matter, and table delimiters. Never
  manually edit generated copy; use its generator and `--check` mode.
- Project READMEs follow one skeleton: What it is / Why / Quickstart /
  Results / Limits / Reproduce (heading wording may vary — map equivalents;
  rename only when a section is genuinely missing).
- Every project README carries a `## Common errors` block: the one failure a
  new runner actually hits, as a `| symptom | cause | fix |` row with
  executable fix commands (the agent-chat template's `specs/operations.md` is
  the model). If the equivalent already exists in the file, skip and say so.
- Diátaxis filing: runbooks are how-to, ADRs (and audits) are explanation,
  the data registry is reference; the ADR index is
  `docs/architecture/adr/index.md`.
- Copy rule: executable commands over click-directives — a reader must be
  able to run what the docs say; one concept per page; code samples first.

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
