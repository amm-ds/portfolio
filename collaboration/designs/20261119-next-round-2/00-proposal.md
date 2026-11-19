# Next round 2: proposal

Date: 2026-11-19
Author: Claude Code (designer)
Status: proposal for owner decision. Nothing here is approved yet.
Inputs: `collaboration/reviews/20261119-next-round-report/00-report.md`, `collaboration/reviews/20261119-sonnet-investigation/00-summary.md`, `collaboration/designs/20261119-next-steps/00-next-steps.md`

## Before round 2: merge decision

`next-round-2026-11-19` is pushed but not merged. Round 2 should start from `main` once that is settled. Decide first whether to merge (see the owner question at the end).

## Proposed items, in order

Offline items first. Each writes new files only. Nothing changes a headline number until the owner reads the result.

| Order | Item | What it does | Cost | Approval needed |
|---|---|---|---|---|
| 1 | **Causal-forest label and stale DESIGN row (10)** | Keep the DR-learner name in copy and state it plainly. Update the stale "causal forests deferred" row in `DESIGN.md`. A real causal forest would need a new dependency, so it is not part of this item. | docs only, $0 | no |
| 2 | **Agent-chat failure triage (14)** | Read the failed cases behind the 24/33 and 26/33 runs and group them by cause. Output: a new triage file. No new model calls. | reading only, $0 | no |
| 3 | **Q4f: rolling-origin MLP vs LightGBM (12)** | Compute check on the committed folds: does the MLP's tie with LightGBM hold across origins? | compute, $0 | yes |
| 4 | **Q4g: cold-start timings (11)** | Re-time cold starts and report per-cell spread from the existing harness. Addresses the warm-only headline. | compute, about 1 day, $0 | yes |
| 5 | **Q4e: open-loop arrival arm (13)** | Add a constant-arrival-rate arm and p99 intervals from raw records. | compute, 1–2 days, $0 | yes |

## Held for later (need an approval or a new dependency)

- **Q3b, RAG warrant check (01).** Hosted, $3 cap. You didn't approve it. Still an option.
- **09 pass^k run.** Hosted, needs an owner cap and a multi-trial design.
- **Q3c, MiniCheck model.** Needs a model download.
- **Q4c, NAB on TSB-AD (03).** Needs a dataset download.
- **Q4d, PyVRP arm (06).** Needs a new dependency.
- **Q4h, mobility weather baseline (07).** Compute, but lower priority.
- **W3 provenance-stamp handoff.** Separate handoff, touches committed results.

## Stop conditions

- A result would change a headline number in copy: stop and write `OPEN_QUESTIONS.md`.
- A committed record would need editing: stop.
- Any hosted call not listed above: stop.

## Owner decisions needed

1. Merge `next-round-2026-11-19` into `main` now, or after you've read the round report?
2. Approve items 1–5 (offline, $0)?
3. Approve or decline the held items, one at a time.
