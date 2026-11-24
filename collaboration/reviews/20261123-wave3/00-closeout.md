# Close-out: Wave 3 — Standardized Roadmaps, Language Pass, M5 Erratic Challenger & UI Card Green Standard

Date: 2026-11-23
Executor: Kimi Code
Handoff: `collaboration/designs/20261123-wave3-roadmaps-language-and-m5/03-implementation-handoff.md`
(approved, 100% local, zero hosted LLM calls). Branch `phase0-infra-2026-11-22`.
No commits, no pushes, no merges.

## Part 1 — Standardized roadmaps (projects 02–13) + language pass

All 12 stories' `roadmap` blocks rewritten to the 5-card lifecycle arc
(Data → Training → Evaluation → Production/Serving → Next), 01-rag-agent as
the structural model: 4 `shipped` + 1 `next`/`blocked`, titles 3–6 words
verb-first with no metric, details ≤90 chars carrying one number or decision.
Every card's facts preserved from the prior copy (traceable to committed
metrics); each `next` gate kept (TSB-AD/VUS-PR, TabPFN dropped, Gehring–
Homberger, 10M real trips, shipping hardware, multi-trial reliability, causal
weather, per-row review persistence, rollout data, live-campaign test).
Programmatic contract check across all 12 files passes.

Language pass: every 02 copy surface reconciled to the owner's current
working-tree metrics (see Part 2); 01's wave-1C copy untouched; no new
short_versions except 02's number sync (276→same length class); registries
regenerated. `cardCopy.ts` 02 achieves updated to 0.6211/−30.4%.

## Part 2 — Demand forecasting: headline reconciliation + erratic challenger

**Headline reconciliation (complete; the checker's 2 pre-existing findings are
cleared).** The copy still quoted the old committed run (0.6161, −31.0%,
0.60/0.10/0.30 weights, 3 origins, 2-selection screen) while the working-tree
`reports_m5_full/metrics.json` records the owner's 10-origin rerun. Updated,
all traceable to metrics.json / evaluation_metadata.json:
champion 0.6211 (−30.4% vs the 0.8929 floor), per-candidate table values,
0.95/0.00/0.05 composition, 9-selection protocol, zero-day 57.2%/58.8%,
per-level total 0.3143 / store 0.461, ~1.35M-second runtime. Surfaces:
`README.md`, `story.yaml`, `docs/projects/02-demand-forecasting.md`, root
`README.md` row, `docs/projects/index.md` row, `cardCopy.ts`, and the pinning
tests in `tests/test_readme_numbers.py` (old-run literals updated to the
current metrics; all pass).

**Erratic challenger (wave-34).** Harness extended in
`src/demand_forecasting/m5_full.py` (new `run_erratic_challenger` + per-candidate
per-origin parquet cache under the gitignored `data_m5/raw/.cache/full_forecasts/`,
new `evaluate-m5-erratic-challenger` CLI, 4 unit tests). The challenger is the
pooled store×category direct arm restricted to the 2,288 erratic dense series
under a Huber objective (alpha 0.9); routing swaps the erratic class into the
committed champion blend; the wave-30 screen decides promotion, the test origin
is scored once.

**Calibration (origin 1877, complete)**: champion 0.7409 vs routed **0.8683** —
a large regression; erratic win-rate vs the naive floor 0.866 → 0.837; zero-day
a wash (0.6365 vs 0.6366). Measured pace ~13.2 h/origin under load.

**Full 9-origin selection pass: RUNNING in background** (task
`bash-fltfczr0`, cache-resumable; ETA ~4–5 days at the measured pace; origin 1
replays from cache). Verdict lands in
`reports_m5_full/erratic_challenger.json`; given origin 1, rejection is the
likely outcome, recorded measured-and-rejected per protocol. The owner can stop
the task anytime; the cache preserves completed origins. **Owner call**: this
pace trades days of compute for a near-certain rejection signal.

**Data note**: `data_m5/raw/m5/datasets/m5.zip` was missing from the working
tree (only the parquet cache remained). Re-downloaded from the canonical
datasetsforecast source; sha256 = the Phase-0 pin `cc704ba1…` exactly.

**Known stale (flagged, no gate reads it)**: `reports_m5_full/demo_payload.json`
still carries old pooled-arm per-series forecasts; a full sync needs a wave-32
catalog rerun (~2.5–3.5 h). Also the README "Validation" bullet still
describes a 3-origin validation harness.

## Part 3 — UI card green standard

Every true card now shares the 3px `--card-accent` left rail (deep green
`#0f766e` in light mode, `#2dd4bf` in dark, via the wave-2 tokens):
`.accent-card` (shared `Card` component: practice/about/bi/glossary cards),
`.study-card`, `.channel-card`, `.bi-card`, `.glossary-card`, plus wave 2's
`.contact-form` / `.wb-notice` rails. The borderless `.offering-card` was
intentionally left without a rail (adding one alone looked broken). Non-button
accent fills (progress bars, sliders, dots) keep `--accent`.

## Part 4 — Gates (verbatim, repo root)

- `check_headline_numbers.py` → `headline-numbers: OK (no unknown drift)`
  (**0 findings — the 2 pre-existing 02 drift items are cleared**)
- `check_short_copy.py --check` → `short copy is single-sourced (39 surfaces across 13 stories)`
- `lint_story_language.py` → `13 stories — 0 errors, 1 warning`
  (01-rag-agent evaluation section 660 words vs the 550 soft budget; warning-level)
- `check_docs.py` → `check-docs: OK`
- `check_demo_contract.py` → `demo-contract: OK`
- `gen_story_short.py --check` → `story short map is current`
- `gen_static_registry.py --check` → `static registry is current`

Web (`apps/showcase-web`): `npm test` → **56 files / 753 tests passed**;
`npm run build` → `✓ built`. Project 02: full suite `uv run pytest -q --no-cov`
→ **exit 0, all tests pass** (including the updated pinning tests in
`tests/test_readme_numbers.py` and the wave-34 challenger tests in
`tests/test_m5_full.py`).

## Files (uncommitted; Claude reviews, validates, commits)

- `projects/02-demand-forecasting/`: `src/demand_forecasting/{m5_full,cli}.py`,
  `tests/test_m5_full.py`, `tests/test_readme_numbers.py`, `README.md`,
  `story.yaml`, `reports_m5_full/erratic_challenger.json`
- `projects/{03..13}-*/story.yaml` (roadmaps)
- `docs/projects/02-demand-forecasting.md`, `docs/projects/index.md`, root `README.md`
- `apps/showcase-web/src/lib/cardCopy.ts`, `storyShort.ts`, `staticRegistry.ts`
- `apps/showcase-web/src/styles/{tokens-base,cards-grids,pages,story}.css`

## Owner decisions next

1. The running selection pass: let it grind (~4–5 days) or stop it — origin 1
   already signals rejection.
2. Catalog rerun to sync `demo_payload.json` (~3 h).
3. Commit strategy for the whole wave (Claude's pass).
