# Design brief: reopen RAG experiment; define "worth it" before closing

Date: 2026-11-22
Designer: Claude Code
Owner: session owner (portfolio repo)
Status: draft, pending owner confirmation of the gate thresholds
Supersedes: the CLOSED declaration in `rag-finalize-2026-11-22` commit `7ef9f30` (local branch only, not merged). The experiment is OPEN.

## Problem

Hosted RAG has a measured unsupported rate, but the measurement is not yet trustworthy and no improvement has been shown:

- The hosted judge's false acceptance is about 0.40 to 0.45 depending on source. Its aggregate figure (0.4536) does not reconcile with its own predictions. The predictions reproduce 0.3966 (kappa 0.6052). The rate is likely an undercount.
- No paired baseline exists on the same 120 sealed questions. The 58-run and 62-run figures are not comparable.
- The limit-8 record has 17 of 120 budget-terminated. The limit-16 run has no checkpoint, so it can lose all results on abort.
- README lines 108-110 (operational retrieval 0.745/0.764/0.718) have no committed source on `main`.

## Goal

Reach a result that is both measured reliably and better than the current hosted baseline, then decide whether it is worth showing.

## "Worth it" gate (proposed defaults; owner to confirm)

The experiment closes only when all of the following hold:

1. **Judge validated.** Its false-acceptance figure reproduces from committed predictions, with an interval, on labelled claims.
2. **Paired improvement.** On the same 120 sealed questions, the candidate minus the current hosted baseline has a 95% CI upper bound below 0 for unsupported rate (that is, a real reduction). If it is only a non-inferiority result, say so and do not present it as improvement.
3. **No new failure modes.** Budget-terminated rows are 0, or each one is explained. False abstention on answerable questions does not rise.
4. **Abstention held.** Refusal accuracy on the 28 unanswerable questions is at least the baseline's.
5. **Grounding 100%.** Every citation and claim references a chunk retrieved in that run.
6. **Reproducible.** Command, config, seed/commit, and per-question traces are committed on `main`, and the headline numbers pass `scripts/check_headline_numbers.py`.

If the gate is not met after the candidate runs, the experiment stays open and the next candidate is chosen. Do not close it on a negative result without owner review.

## Candidate directions (ranked; not yet decided)

| # | Direction | Why | Cost | Evidence needed |
|---|---|---|---|---|
| A | Validate the judge; report the unsupported rate with its bias bounded | Without it, no comparison means anything | Low (committed predictions) | Reproduction table |
| B | Checkpointed limit-16 run | Removes budget cutoffs, the main known failure | Medium ($1.5–1.8 estimate, cap $2.50) | Command, checkpoint design, host check |
| C | Retrieval fix for operational-retrieval claims | README lines 108-110 unsourced; misses cause unsupported answers | Medium | Retrieval recall on sealed labels |
| D | Tighter verify (claim repair or drop) | Targets unsupported claims directly | Medium–high (touches verify loop) | Paired run vs baseline |

Order: A, then B, then C or D based on A's results. Each candidate is a separate, owner-approved handoff. No architecture change is made without its own design.

## Constraints

- Hosted calls only, within caps approved per run. Each run has a stated cap.
- No change to `src/` or copy without an approved handoff.
- Nothing merged or pushed without owner approval. The G4 data branch stays unmerged until the owner decides.
- Project 02 metrics: out of scope.

## Open questions for the owner

1. Confirm the gate thresholds above, or change them. In particular: is a CI upper bound below 0 required, or is non-inferiority enough?
2. Confirm the order A, B, then C or D.
3. Approve merging the G4 data branch into `main`, so the baseline is reproducible from `main`?
