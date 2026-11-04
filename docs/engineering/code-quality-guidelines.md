# Code Quality Guidelines

This repository is reviewed against three public skill frameworks, vendored
under [`skills/`](skills/) and distilled here. Agents and contributors apply
them to every non-trivial change.

## 1. Ponytail — the smallest complete change

> The best code is the code never written.

Before writing anything, take the first option that fully works:

1. **Does it need to exist?** Skip features, options and flexibility nobody
   asked for; name the skipped part in one line.
2. **Already in this codebase?** Use the existing helper/component/pattern
   the way surrounding code does.
3. **Standard library or platform feature?** Use it, unless the project has
   its own house wrapper.
4. **Installed dependency?** Use it. Never add a dependency for a few lines.
5. **One line a reader gets at a glance?** One line.
6. Otherwise: the minimum code that works.

Rules of the road:

- Be lazy about the solution, never about the change: finish every part the
  task needs, including callers, tests and fixtures the change breaks.
- Deletion beats addition. No wrapper, config, conversion or "for later"
  code nobody asked for.
- Comment only the *why* the code cannot show, in one line.
- Bug fix: grep every caller of the function you touch, fix the root cause
  once in the shared code.
- Never cut: validation at trust boundaries, error handling that prevents
  data loss, security, accessibility, or anything the user asked for.
- New non-trivial logic (a branch, a loop, a parser, money or security)
  leaves one small test or an assert-based self-check. Trivial changes need
  none.
- A shortcut with a known limit gets a comment: `shortcut: <limit>, <when to upgrade>`.
- End the work summary with what you skipped and any risk the owner must know.

## 2. Thermo-nuclear review — structural ambition

The bar is not "it works"; the bar is "no clear structural regression and no
visible path to something dramatically simpler left untaken".

- **File size:** a change must not push a file from under 1,000 lines to over
  1,000 lines without a compelling reason — extract first.
- **No spaghetti growth:** new ad-hoc conditionals or special cases bolted
  onto unrelated flows are a design problem, not a nit. Push the logic into a
  dedicated abstraction.
- **Code judo:** prefer the reframing that deletes whole branches, helpers or
  layers over the refactor that rearranges the same complexity.
- **Canonical layer:** feature logic lives in the right package/module; reuse
  the existing canonical helper instead of a near-duplicate.
- **Boundaries and types:** question `any`/`unknown`/cast-heavy code and
  silent fallbacks; make the invariant explicit at the boundary.
- **Orchestration:** flag serialized independent work and non-atomic updates
  when the cleaner structure is obvious.

Findings are reported in order: structural regressions → missed
simplifications → branching complexity → boundary/type problems → file size →
modularity → legibility. Few high-conviction findings over many cosmetic nits.

## 3. pstack principles — the working set

| Principle | Rule |
|---|---|
| laziness-protocol | Bias toward deletion and the smallest change that solves the problem. |
| subtract-before-you-add | Remove dead weight and stub references first; build on the simpler base. |
| minimize-reader-load | Collapse one-caller wrappers; shrink mutable scope; count the layers between question and answer. |
| boundary-discipline | Guards concentrate at system boundaries (CLI, config, network); internals trust the types. |
| type-system-discipline | Make illegal states unrepresentable; parse external data at boundaries. |
| prove-it-works | Verify against the real artifact — run it, read the value, inspect the diff — never "it compiles". |
| fix-root-causes | Fix where the system first went wrong; a guard is a fix only for legitimate state. |
| test-behavior-not-implementation | Assert what users observe, so tests survive internal refactors. |
| explain-the-number | Before trusting a measured number: find what limits it and rule out that it measured something else. |
| encode-lessons-in-structure | Prefer a lint, script or check over a paragraph of advice. |

## Repo-specific enforcement

Every quality pass ends with the gates it touched green:

- Python: `uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps`
- Tests: `uv run pytest -q` (or the affected suites)
- Web: `cd apps/showcase-web && npm test && npm run lint && npm run build`
- Content: `uv run python scripts/lint_story_language.py`,
  `uv run python scripts/check_short_copy.py --check`,
  `uv run python scripts/check_demo_contract.py`,
  `uv run python scripts/gen_static_registry.py --check`,
  `uv run python scripts/gen_story_short.py --check`,
  `uv run python scripts/gen_route_manifest.py --check`

## Sources

- `skills/ponytail/SKILL.md` — [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT)
- `skills/thermo-nuclear-code-quality-review/SKILL.md` — [cursor/plugins](https://github.com/cursor/plugins/tree/main/cursor-team-kit/skills/thermo-nuclear-code-quality-review)
- pstack principles — [cursor/plugins pstack](https://github.com/cursor/plugins/tree/main/pstack)
