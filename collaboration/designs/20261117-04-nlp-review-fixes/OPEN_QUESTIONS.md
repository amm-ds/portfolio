# OPEN QUESTIONS — 04 NLP cascade paired interval

Date: 2026-11-19 (overnight queue, item 3)
Executor: Kimi Code

## Blocked step

Handoff step 1 (blocker): "Compute a paired bootstrap interval on the
difference in macro-F1 (cascade minus transformer) on the fresh 1,000 split,
using the existing committed predictions."

## Why it is blocked

A paired bootstrap needs per-row cascade predictions on the fresh 1,000.
What is committed and what is not:

- `reports/llm_cascade.json` carries split-level aggregates only
  (baseline/cascade macro-F1, accuracy, `n_reviews` per split). It has no
  per-row predictions.
- The per-row transformer (baseline) predictions are reproducible offline
  (committed `distilbert_fulldata.pt`, committed test partition, seeded fresh
  draw documented in `llm_cascade.json.provenance.fresh_holdout`).
- The per-row LLM review decisions — which of the 22 sub-τ rows changed to
  which label — are **not committed anywhere** (checked `reports/`, `data/`,
  `tests/`, `apps/showcase-api` payloads). Reproducing them requires new
  hosted `kimi-for-coding` calls, which the overnight hard limits forbid.

Without the 22 per-row decisions the paired interval is not identifiable from
committed artifacts (multiple decision patterns yield the same aggregate
fresh macro-F1 0.9539265 but different bootstrap distributions).

## What was done instead (per master-report correction 2)

Master report correction 2: "Report as 'no measurable change' unless a paired
interval excludes zero." With no interval computable, all cascade copy was
reworded from "lifts/small gain" to "no measurable change (Δ macro-F1 +0.001)"
— see `story.yaml`, `README.md`.

## Options for the owner

1. Re-run the cascade once under an approved hosted budget and persist
   per-row decisions (extend `llm_cascade.json`) so the interval is
   reproducible offline thereafter.
2. Or accept the "no measurable change" wording permanently and downgrade
   handoff step 1 to a documented limitation.

Remaining handoff steps 2–7 were completed (rewording, int8 table split,
routing test, rounding, licence, storyShort regen).
