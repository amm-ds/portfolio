# Full Repo Review — 2026-11-06

Scope: backend and frontend code, organization, infrastructure, practices,
and the presentation layer. Every finding cites evidence; every fix lists
its gate. Priorities: P1 structural, P2 hygiene, P3 polish.

## Verified strengths (do not regress)

- **Terminal design system is coherent**: study-card pattern shared by
  demos/experiments/apps, channel cards + values-only fact cards shared by
  Contact and About, a section-title family (white, green `>` marker) used
  consistently, green/blue accent discipline, mono metadata.
- **Truth-in-copy is enforced**: `check_short_copy.py` (52 surfaces),
  `lint_story_language.py` (13 stories 0/0), `check_demo_contract.py`,
  generated registries with `--check` modes. Numbers in cards come from
  committed metrics.
- **Gates exist and run**: ruff + mypy strict (215 files), 13 project
  suites (~1,250 tests), 432 web tests, axe a11y job, mkdocs strict,
  `check_docs.py` (new CI step).
- **Diagram lane is real**: mermaid pre-built SVGs (53 sources) plus the
  React Flow v12 interactive lane with typed specs, house shapes, hover
  neighborhood highlighting, and per-node committed-facts inspector.
- **The agent-chat template is properly isolated**: own lockfile/venv/suites;
  the root mypy sweep and root pytest correctly exclude it.
- **Dependabot is quiet** (major-ignore policy in `.github/dependabot.yml`).

## P1 — structural debts to retire

### B1. `apps/showcase-api/src/showcase_api/main.py` (1,142 lines)

Evidence: thermo-nuclear's 1k-file bar. The API agent already mapped the
seams and their monkeypatch fixtures. Plan (approved): extract `spa.py`
(web-dist serving) and `live.py` (LiveGuard + bounded timeouts), re-point
fixtures in the same wave, endpoints byte-identical. `demos.py`/`served.py`
follow only if equally cheap.

### B2. `apps/showcase-web/src/styles.css` (4,675 lines)

Evidence: single-file sprawl; the earlier proposal was specced but never
executed. Split into seven partials (tokens-base, shell, cards-grids, story,
figures, pages, demos) behind a manifest `@import` entrypoint (Vite inlines
at build — zero runtime change). A test helper concatenates partials so the
~15 CSS-asserting tests keep asserting identical text.

### B3. The agent-chat template's tests never run in CI

Evidence: `apps/agent-chat/conftest.py` deliberately skips the suite outside
its own directory (correct isolation), but no CI job exists for it. Add an
explicit job (own uv lock, own venv) in `.github/workflows/ci.yml`.

### B4. Headline-metrics storage convention is mixed (11/12 vs the rest)

Evidence: 11/12 keep `reports/metrics.json` as DVC outs (absent from a
fresh CI checkout), everyone else commits it to git. This already cost one
CI failure (diagram fact-check). Write the convention down
(repo-conventions): **headline metrics belong in git** (small files);
large derived data stays DVC-tracked. No retroactive change to 11/12.

## P2 — hygiene candidates (only if cheap and provable)

- **Shared-lib extraction**: `portfolio_core.serving` (the SERVING.md
  builders in 02/05/07) and `portfolio_core.demo_payload` (02/05/10
  precomputed-payload pattern). Previously flagged by the projects agent as
  owner-decision items; keep them small, with tests.
- **Intermittent web-test flake** (1-in-~5 under load locally): never named
  in CI. Track via an issue rather than chasing; the axe job's failure was
  runner-side uv cache pruning, not a violation.
- **`docs/` nav is convention-driven** (auto-include). The `llms.txt` pair
  now covers AI readers; keep it current as pages are added (conventions
  already codify this).

## P3 — presentation refinements (approved scope, ordered by leverage)

1. Home terminal/hero polish (width, availability badge, focus vocabulary).
2. Projects index hierarchy and the compact apps card.
3. Case-study rhythm: business summary first, figure links, lean dropdown.
4. Services process visual (horizontal, revisions 05) + logo chips.
5. Contact/About: slim phone gate, centered fact cards, horizontal
   engagement roadmap, About practices matrix + centered timeline.
6. Design-token sweep: spacing scale, accent logic, focus-visible,
   reduced-motion, hover lift only on links.

## Owner decisions to respect (not ours to change)

- DNS for `alejandromerida.dev` (the only go-live blocker).
- `gh auth refresh -s user` for the account bio (text ready).
- Deliberate react-19 / vite-8 upgrades (ignored in dependabot by design).
- The 02 full-panel re-run: wired, test-proved, deferred until its verdict
  lands (the gate protocol is in place).
