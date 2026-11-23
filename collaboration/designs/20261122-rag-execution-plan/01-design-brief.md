# Design brief: execution plan for the RAG roadmap (project 01)

Date: 2026-11-22
Designer: Claude Code
Owner: session owner (portfolio repo)
Status: draft, owner approval requested. Builds on `collaboration/designs/20261122-rag-roadmap/01-design-brief.md` and `collaboration/designs/20261122-rag-phase0-infra/03-implementation-handoff.md` (committed as 791cf78 and 4f4660c).

## Problem

The data side is in place: final_v3 (120, accepted, frozen in 4f4660c), dev_v1 (20, tuning-derived), and the run infrastructure. Nothing has been measured yet. The roadmap needs a validated judge before any F1 counts, and a retrieval baseline before any lift can be attributed.

## Goal

Produce a measured retrieval baseline and the first lift on dev, with a validated judge ready for the end-to-end step, without spending on hosted models.

## Decisions taken (owner, 2026-11-22: "1 sonnet, proceed with recoms")

1. **Judge labels:** Sonnet drafts the labels; the owner checks a sample. Claude labelling is outside the Kimi $3 cap and needs its own owner budget (see the handoff, step 1).
2. **Retrieval first:** chunking, embeddings and reranker run locally on dev_v1, no hosted spend.
3. **Dev discipline:** iterate on dev_v1 and grow it (20, 40, 65) only when a change looks promising. final_v3 is used once per candidate, as the final check.
4. **Gate per change:** a retrieval change is kept only if recall@5 improves on dev and the final_v3 check does not show a drop.
5. **End-to-end last:** a separate handoff, with kimi-for-coding, soft stop $2.00 and hard stop $3.00 on estimated spend.

## Success criteria for this plan

- A pinned retrieval baseline on dev_v1 (recall@5, MRR, with the config hash).
- A judge calibration set of about 150 labelled claims, with Sonnet's agreement with the owner's sample reported.
- At most three retrieval changes measured, each recorded in `reports/experiment_log.json` with its before and after numbers.
- No hosted calls in steps 0 to 4.

## Not in scope

- Any end-to-end run with hosted models.
- Any change to `src/rag_agent/`, prompts, or `params.yaml` except through the sweep configs named in the handoff.
- Merges, pushes, or project 02 changes.
- The 34 uncommitted working-tree changes (see handoff, step 0).
