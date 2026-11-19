# Execution plan for Kimi: copy, roadmap, apps, RAG, and the conflict decisions

Date: 2026-11-19
Designer: Claude Code (decisions adopted from the Sonnet conflict resolutions)
Executor: Kimi Code (owner runs it)
Owner: amm-ds
Status: Q1, Q1b, Q2, Q3a and Q5 APPROVED by owner on 2026-11-19 (offline items, copy and roadmap). Q3b, Q3c and all Q4 items PENDING owner approval and must not run.

Inputs:
- Decision record: `collaboration/designs/20261119-open-questions-closed/00-decisions.md`
- Third-pass plan: `collaboration/reviews/20261119-third-pass/00-plan-articles-roadmap-cards-rag.md`
- Conflict resolutions: `collaboration/reviews/20261119-conflict-resolution/00-resolutions.md`
- Investigation: `collaboration/reviews/20261119-sonnet-investigation/00-summary.md`

## 0. Standing rules (all items)

- No git mutations (add, commit, push, branch, stash, reset). The owner commits.
- No deploys. No `.env`, permissions, or config changes.
- Hosted model calls: only in item Q3, capped at **$3 total** on `kimi-for-coding` (the cheapest approved model). Stop at $2.50 and report. No other hosted calls.
- No change to any headline number, except where a committed artifact contradicts the copy, and then only as listed in the decision record. Each such change is named in the report with its file path.
- No full M5 panel rerun. Do not change the 360 px per-row minimum. Do not compute the NAB official score. Do not add `quality_quant` to `DOCS_FIGURES`.
- Generated files change only through their scripts. Committed records under `projects/*/data/` are not edited in place.
- Do not cite any PyVRP number in any copy surface.
- Stop and write `OPEN_QUESTIONS.md` beside this plan if an item's stop condition applies.

## 1. Conflict decisions adopted (from the Sonnet resolutions)

| Conflict | Decision | Effect on execution |
|---|---|---|
| 06 PyVRP tables | Two tables in one paper. The 0.40/0.32/0.29% numbers are the 1000-customer VRPTW table; the 0.27/0.28/0.16% numbers are the CVRP X-instance table. No PyVRP number goes into any copy. | Q1 adds nothing about PyVRP. Any future PyVRP arm names its table. |
| 03 VUS-PR | "Disclose N" adopted: state the run count and seed spread with every VUS-PR result. The "gamed on NAB" wording is softened to "inflates under large best-of-N selection". | Q1 copy for 03. Q4 item (VUS-PR on TSB-AD) stays pending. |
| 12 TabPFN licence | TabPFN-2 weights fall under Prior Labs License v1.1 (Apache-2.0 plus attribution; commercial use allowed). TabPFN-2.5 is not used. Attribution "Built with PriorLabs-TabPFN" is displayed where the challenger is shown. | The TabPFN-2 handoff (already approved) applies. |
| 02 M5 rolling origins | Not verified. Do not claim rolling origin is the M5 standard. | Q1 copy must not contain that claim. |
| 14 agent-chat denominator | The article's 108/108 is correct for kimi-for-coding (16 cases, 3 repetitions). Add one sentence about the other two model runs, reported as single runs: k3-256k 26/33, k3.1-pro 24/33. | Q2. |
| 03 TSB-AD count | The NeurIPS 2024 abstract states 40 algorithms. The repo README lists 35 in its tables. Use 40 with the source, and note the README mismatch for the owner. | Q1 copy for 03 (only if the count appears). |
| 10 Qini/AUUC | Keep the unnormalised Qini (area between curve and random line). State the definition beside each number. Name the "AUUC" label in the design doc as the same quantity. Normalised form is out of scope. | Q1 copy for 10. |

## 2. Items

### Q1 — Copy, roadmap and decision-record fixes (APPROVED)

Source: the approved Q1 plan (third-pass §B and §C), plus the decision record items 1–8.

Do:
1. **Roadmap cards** (shipped only, finalized steps). Rewrite the 11 titles listed in third-pass §B. Keep each detail at 90 characters or fewer. Keep 3–5 shipped cards per project.
2. **Naming:** 04 names its split in both roadmap and short copy (the fresh split for the 0.953 → 0.954 claim; the test split 0.9460 only where it is labelled test). 07 uses one model name everywhere: "served GBM" (copy) replaces "xGB" in the roadmap.
3. **Decision record fixes** (from `00-decisions.md`, items marked Q1):
   - 03: threshold caption and Conclusions use "17 of 120 flags hit real incidents, 14.2% precision". Remove "115 flags" and "14.8%".
   - 06: replace "8 references" with the count from `reports/results.md`: ALNS has negative gaps on 5 instances (6 counting `alns_fleet`). Name the table. Keep the 8-solver ladder claim.
   - 09: rewrite the live claim to: "Live held-out run (2026-11-19): 13/13 answers; refusals 6/6 under the live grader, with h19 a calculator-guard error; 19/19 budgets." Link `collaboration/reviews/20261118-live-confirmation/comparison.md`. Leave the legacy 5/6 as the legacy recorded run. Remove "8 unplanned calls".
   - 10: "+70%" everywhere (not "+69%"). Keep "+$2,812" with "revenue minus send cost" named.
   - 12: card 3 title shortened to "Gap to the floor holds under resampling." Replace the dangling "see research deltas" pointer with "TabPFN-2 challenger pending; see the project README."
   - 13: "up to 15%" becomes "13.8% at the c64 throughput cell; p50 medians differ by at most 4%". Remove "3.3 GB CUDA stack", "12.8 GB earlier build", and the "~20%" slope threshold.
   - 02: remove the spike-capture values from story and cards (keep in DESIGN.md). Remove any rolling-origin "standard" claim.
   - 04: remove the ECE pair and "37% cut" from the roadmap card and story body (keep in DESIGN.md). Retitle the card to "Calibrated probabilities with one temperature."
   - 11: remove "tracing made pandas's group-by 4x slower".
4. **03 VUS-PR wording:** add "run count and seed spread" beside each VUS-PR result; soften "gamed on NAB" to "inflates under large best-of-N selection".
5. **Cross-check:** any model name, split name or metric name used in one article must match its use in the roadmap and short copy.

Do not:
- Change a figure file by hand. The 10 `profit_frontier` annotation ($6,698 → $6,838) is a figure fix in Q1b.

Gates:
- `uv run python scripts/lint_story_language.py`
- `uv run python scripts/check_docs.py`
- `uv run python scripts/check_short_copy.py --check`
- `uv run python scripts/gen_story_short.py --check` (regenerate with the script if it fails; never hand-edit)
- `uv run python scripts/check_headline_numbers.py`
- `cd apps/showcase-web && npm test && npm run lint && npm run build` (roadmap rendering and `storyShort.ts` changed)

Stop: a fix would change a headline number not listed above; a committed record would need editing.

### Q1b — Figure regeneration for 10 (APPROVED)

- Regenerate `projects/10-uplift-experimentation/reports/figures/profit_frontier` through the project's own CLI (`evaluate.py` path). The annotation must read $6,838 (T-learner), matching `reports/metrics.json` and the story table. Do not hand-edit the HTML or JSON.
- Gates: project 10 tests, `check_headline_numbers.py`, `gen_static_registry.py --check`.

### Q2 — Apps content review (APPROVED)

Scope: `agent-chat` and `document-intelligence` articles (`apps/showcase-web/src/pages/AgentChatArticle.tsx`, `DocumentIntelligenceArticle.tsx`) and their card copy in `apps/showcase-web/src/lib/apps.ts`.

Do:
1. Check every number in the article prose against its committed report (`apps/agent-chat/reports/evals-kimi-for-coding.md` and the other two model reports; `apps/document-intelligence/reports/*`). List each number and its file in the report.
2. Agent-chat evaluation section: add one sentence that the two other model runs were single runs, 26/33 (k3-256k) and 24/33 (k3.1-pro), and that their grader sets differ from the 16-case suite. Do not change the 108/108 claim.
3. Document-intelligence: remove any sentence that reads as a production accuracy claim. The article already says this; check the card copy agrees.
4. Replace provider names in the agent-chat "does" line with "a hosted or local model, with fallback" so the card does not age.
5. Section headings and subtitles follow the same format as the experiment articles.

Gates: the web gates above; `check_docs.py`; `lint_story_language.py` if any story file changed.

Stop: a number in the article has no committed source.

### Q3 — RAG: offline calibration, then a capped warrant check (PARTLY APPROVED)

Q3a (APPROVED, offline, no hosted calls):
- Use the committed 194-claim label set for project 01 (in `projects/01-rag-agent/` judge calibration artifacts). Measure false-acceptance and kappa for each committed judge, and report them with intervals. The Sonnet finding says the committed local judges accept false claims about 44–45% of the time and have kappa about 0.54.
- Write the result to `projects/01-rag-agent/reports/judge_calibration_report.json` as a **new** file. Do not overwrite existing records.
- Do not change the verify-on claim in copy until the owner reads this result.

Q3b (PENDING owner approval, capped at $3 hosted): a warrant-strength judging run on the sealed set, using `kimi-for-coding` only. Do not start it until the owner approves Q3b and confirms the cap.

Q3c (PENDING owner approval): a MiniCheck-family local checker. It needs a model download, so the owner must approve it first.

Gates: `uv run pytest -q projects/01-rag-agent`, `ruff`, `mypy`, `check_headline_numbers.py`.

### Q4 — Compute-only experiments (PENDING owner approval, do not start)

Listed for the owner to approve one at a time. Each writes a **new** report file, never an overwrite.
- Q4a: 10 Uplift: causal forest, T-, X- and two-model learners on the committed folds; Qini (unnormalised, formula stated) and AUUC with intervals.
- Q4b: 04 AG News: risk-coverage curve and AURC on the fresh holdout.
- Q4c: 03 NAB: VUS-PR on a TSB-AD subset. Needs a dataset download, so pending.
- Q4d: 06 PyVRP as an in-repo arm, vehicles-first ranking. Needs a new dependency, so pending.
- Q4e: 13 model serving: open-loop arrival arm and p99 intervals from raw records.
- Q4f: 12 rolling-origin MLP vs LightGBM check.
- Q4g: 11 data engineering: cold-start timings and per-cell spread.
- Q4h: 07 mobility: seasonal-with-weather baseline and adaptive borough band.

### Q5 — TabPFN-2 challenger (APPROVED, already handed off)

Run `collaboration/designs/20261119-tabpfn2-challenger/03-implementation-handoff.md` after Q1 is complete (it changes the same project 12 files). Attribution and licence copy are required by that handoff.

### Q6 — Provenance stamp (W3) (PENDING, separate handoff)

Not in this plan. It changes committed results files, so it needs its own handoff and diff review after Q1.

## 3. Order

1. Q1 (copy and roadmap), then Q1b (figure regeneration).
2. Q2 (apps content review).
3. Q3a (offline RAG calibration).
4. Q5 (TabPFN-2 challenger), which touches project 12 after Q1.
5. Stop. Report. Wait for owner approval before Q3b, Q3c and any Q4 item.

## 4. Report

One report at `collaboration/reviews/20261119-execution-report/00-report.md`:
- one row per item: status, files changed, commands run, gate results actually run, open questions;
- every number changed, with the committed file it was checked against;
- the hosted spend (should be $0.00 for this plan, since Q3b is pending);
- what remains for the owner to review or commit.

Quote numbers exactly. Do not claim a gate passed unless you ran it.

## 5. Owner decisions needed

1. Approve Q1, Q1b, Q2, Q3a and Q5 to run now (Q3a and Q5 are offline).
2. Approve or decline Q3b (hosted, $3 cap) and Q3c (model download).
3. Choose which Q4 items to approve, one at a time.
4. Decide whether the TSB-AD README mismatch (35 listed vs 40 stated) gets fixed now or later.
5. Re-run full `pytest` from scratch before you commit.
