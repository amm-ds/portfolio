# UI and apps fixes report — H1–H8

Date: 2026-11-19
Executor: Kimi Code (per `collaboration/designs/20261119-ui-and-apps-fixes/00-review-and-handoff.md`,
owner-approved H1–H8 with section-4 defaults: H6 option (a) 2×2, H5 summary by case kind).
No git mutations, no deploys, no hosted calls. The 360 px per-row minimum is
untouched; no headline number changed (stop conditions did not trigger).
Verified against the local dev server (`:4321` → API `:8002`).

## Summary

| # | Item | Status | Files changed | Screenshots (375 / 1280) |
|---|---|---|---|---|
| H1 | Projects page order apps → experiments → demos | done | `src/pages/ProjectsIndex.tsx` (+ render-order test updates) | `375-h1-projects-index.png`, `1280-h1-projects-index.png` |
| H2 | "01 Background" spacing | done | `src/components/AppArticle.tsx`, `src/components/StorySection.tsx`, new `src/__tests__/AppArticle.test.tsx`, updated `StorySection.test.tsx` | `1280-h2-agent-chat.png`, `1280-h2-doc-intel.png` |
| H3 | Subtitles muted token both themes | done | `src/styles/story.css` (`.section-subtitle` → `var(--muted)`) | dark visible in H2 shots; light: `1280-h3-subtitle-light.png` |
| H4 | DI committed-result table via markdown path | done | `src/pages/DocumentIntelligenceArticle.tsx` (raw `<table>` → pipe table via `renderMarkdown`), new `src/__tests__/DocumentIntelligenceArticle.test.tsx` | `375-h4-di-table.png` |
| H5 | Agent-chat eval summary table from the committed report | done | new `scripts/gen_agent_eval_summary.py` + generated `src/lib/agentChatEvalSummary.ts`, `src/pages/AgentChatArticle.tsx`, new tests (generator + article) | `1280-h5-agent-eval-table.png` |
| H6 | `nab_tune_surface` 2×2 (option a) | done | `projects/03-anomaly-detection/src/anomaly_detection/nab_tune.py`, regenerated `reports/figures/nab_tune_surface.*`; `nab_tune.json` back to HEAD parity (null-placeholder writer fix in `nab.py` — see H6 note), converter bottom-band fix in `plotlyToECharts.ts` | `375/1280-h6-nab-tune-before.png`, `375/1280-h6-nab-tune-after.png` |
| H7 | Diagram cylinder aspect + phone centering | done | `src/components/diagrams/FlowDiagram.tsx` (`preserveAspectRatio="xMidYMid meet"`; phone viewport centres the laid-out bounds, initial + resize) | `375-h7-diagram-dark.png`, `390-h7-diagram-dark.png`, `375-h7-diagram-light.png` |
| H8 | Figure sizing audit (20 multi-panel figures) | done — 4 fixed, 2 converter improvements, rest clean | `nab.py` (03), `eda.py` (05), `figures.py` (12), `figures.py` (13), regenerated figures; converter `tickformat` support (`.3g`, `%b %d`) | before/after set under `375-h8-*` |

## H1 — page order

`DemosSection` moved after the experiments block; anchor nav now apps →
experiment rows → live demos; three stale comments updated. Two pre-existing
tests encoded the old order and were updated (anchor list + demos-after-
experiments assertions); a new assertion locks the block order. `ProjectsIndex`
suite: 35 passed.

## H2 — title spacing

Root cause: JSX whitespace-newlines between elements are stripped, so the
`sec-num` span touched the title text; the local CSS margin masked it but prod
rendered "01Background". Fixed with an explicit text node in
`AppArticleSection` and `StorySection` (the latter guarded so the optional
index renders no leading space). One pre-existing test expected the buggy
string — updated. New `AppArticleSection` test locks "07 Evaluation".

## H3 — muted subtitles

`.story-section .section-subtitle` now uses `var(--muted)` (#94a3b8 dark /
#4e6276 light — both existing theme tokens), comment updated. Verified in the
H2 dark screenshots and a dedicated light-theme shot.

## H4 — DI table

The "Committed live result — 2026-11-08" table is now a markdown pipe table
rendered by `lib/markdown.tsx` — `div.table-scroll > table.data-table`, the
same chrome as every other article table. Numbers untouched. New DOM test
asserts the chrome; measured horizontal page overflow at 375 px: **0 px**.

## H5 — agent-chat summary table

New generator `scripts/gen_agent_eval_summary.py` parses the committed
`apps/agent-chat/reports/evals-kimi-for-coding.md` (per-case pipe table +
totals line) and bakes `src/lib/agentChatEvalSummary.ts` (mirrors the
staticRegistry pattern; `--check` mode; deterministic). The article's
Evaluation section renders a `DataTable` from that module: answer 63/63
(58%), refuse 18/18 (17%), tool_choice 27/27 (25%), total **108/108** with
**48 executions** (16 cases × 3 repetitions) — exactly the report's totals.
Generator tests: fixture with one fail row (counts 2/3), the real committed
report (108/108, 48), render determinism.

## H6 — nab_tune_surface 2×2

- Source: `make_subplots(rows=1, cols=4)` → 2×2 (`vertical_spacing=0.14`),
  height 460 → 720, x-axis title restricted to the bottom row (it collided
  with the lower panels' titles), ring/star markers removed from the legend
  (the caption already explains them; they overlapped panels at 335 px).
- Regenerated via `cli nab-tune`: all committed values identical
  (deterministic re-solve; log confirms 35→35, 0.533→0.533).
  **Correction (owner review):** the first regeneration also added ~612 lines
  of null `range_pr_auc`/`pa_k_*` keys to `nab_tune.json`. Cause: the shared
  `_aggregate` in `nab.py` emitted those keys unconditionally, and sweep/tune
  rows (via `nab_sweep._base_row`) never carry them — null placeholders, not
  enrichment. Fixed at the writer (`_aggregate` now reports range-PR keys only
  when rows carry them), `nab-tune` re-run: `nab_tune.json` is byte-identical
  to HEAD again, zero enrichment keys remain; `nab_metrics.json` aggregates
  unchanged (headline rows carry real values). Gates: 03 suite 111 passed,
  ruff/format/mypy clean, `check_headline_numbers.py` OK.
- Converter: the narrow-legend bottom band now also reserves space for
  bottom-row x-axis names (+84 px when present) — without it the relocated
  legend overlaid the wrapped names.
- Result: before = four compressed panels with side text in the plots;
  after = four legible panels, clean titles, legend below. 03 suite exit 0;
  `check_headline_numbers.py` still OK.

## H7 — mobile diagrams

- Cylinder icon: `preserveAspectRatio` `none` → `xMidYMid meet` — no more
  vertical smear.
- Phone view (< 480 px canvas): the viewport x now centres the laid-out
  bounds (`(canvasWidth − bounds.width) / 2`, both on open and on resize)
  instead of left-edge anchoring; pan unchanged.
- `FlowDiagram` suite: 15 passed. Screenshots at 375/390 px dark + 375 px
  light: cylinder proportions correct, content centred.

## H8 — figure sizing audit

Inventory: 20 committed figures with multi-panel layouts (≥2 rows or ≥3
columns); 11 are user-facing story figures. Screenshot method: every flagged
figure captured at 375 px on its project page; fixes only where content
overlapped:

| Figure | Verdict | Fix |
|---|---|---|
| nab_tune_surface (03) | fixed in H6 | — |
| family_gap (06) | already clean (narrow-legend work) | — |
| sample_series / m5_full_sample_series (02) | clean | — |
| actual_vs_pred_top5 (07) | dense but no overlap | — |
| eda_segment_profile (10) | dense labels, no plot overlap | — |
| bootstrap_ci (12) | clean | — |
| **nab_timelines (03)** | overlapped | top-row x labels hidden; y ticks `.3g`; converter now honours `tickformat` (`.3g` compacts floats, `%b %d` renders "Feb 1"/"Sep 15") — before: raw floats ran into the row-2 titles; after: compact labels + real dates. Mild corner crowding of the long series names remains (documented, cosmetic). |
| **eda_churn_profile (05)** | overlapped | panels 2/3 x-axis names removed (subplot titles already name them; trace data verified byte-identical) |
| **rentals_by_hour_season (12)** | overlapped | "hour of day" x title on the bottom row only |
| **footprint_cost_bars (13)** | overlapped | short bar labels ("torch"/"ONNX") in this dense 1×3 |

All four regenerated with their own project commands; 03/05/12/13 suites all
exit 0; churn bar values verified identical (0.4271 month-to-month = the
committed 42.7%); provenance `_meta` restamped on 05/12/13 metrics.

## Gates actually run

- Per item: web `npm test` targeted files + `tsc --noEmit`; H6/H8: project
  suites (`03`, `05`, `12`, `13` — all exit 0), ruff/format/mypy,
  `check_headline_numbers.py` (OK, no unknown drift, after every regeneration).
- Final sweep: web `npm test` **752 passed (56 files)**, `npm run lint`
  clean, `npm run build` ✓ · `ruff check .` All checks passed ·
  `ruff format --check .` already formatted · `mypy libs projects apps`
  Success · `check_short_copy` single-sourced · `check_demo_contract` OK ·
  `gen_static_registry --check` / `gen_story_short --check` /
  `gen_route_manifest --check` current · `lint_story_language` 0/0 ·
  `check_docs` OK · `gen_agent_eval_summary --check` OK.
- `uv run pytest -q` (full repo): **exit 0, 97.69% total coverage**.

## Stop conditions

Neither stop condition triggered: the 360 px per-row minimum is untouched
and no headline number changed (verified per regeneration: 03 0.527/0.157/
1,609; 05 601/644/1,035 + 42.7% bars; 12 25.4/83.2; 13 unchanged artifacts).

## Screenshots

All 29 under `screenshots/` — `375-*` and `1280-*` per item, H6 and the four
H8 fixes with `-before`/`-after` pairs.
