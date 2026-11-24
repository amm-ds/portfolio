# Architecture proposal: measurement path for the RAG roadmap

Date: 2026-11-22
Designer: Claude Code
Status: draft, for owner review with the design brief.

## Summary

Keep the pipeline unchanged. Measure it in two layers: retrieval on local sweeps (cheap, repeatable), and answer quality through a judge that is first validated on labelled claims. Hosted spend is confined to the final end-to-end step.

## Components

| Layer | What it measures | Data | Cost |
|---|---|---|---|
| Retrieval | recall@5, MRR, token cost | dev_v1, then the 65-question tuning set; final_v3 once per candidate | local |
| Judge | agreement with labels; false acceptance with Wilson interval | judge calibration set (about 150 claims) | Claude labels (owner budget); judge local |
| End-to-end | per-question F1, errors | dev_v1 first, final_v3 once | hosted, capped (later handoff) |

## Judge calibration set

- Source claims come from tuning-65 gold chunks and dev_v1 gold chunks only. final_v3 and sealed-120 are not used for labels.
- Each item is a claim with its cited chunk. Two kinds: supported (paraphrase of a fact in the chunk) and unsupported (a plausible wrong or unstated claim). Target roughly half each.
- Sonnet labels every item with the chunk text as evidence. The owner checks a random sample of 30 and records agreement.
- The labelled set is committed under `reports/judge_calibration_v2/`, with the labeller model and prompt hash.

## Experiment log

`reports/experiment_log.json` gets one row per change: change, config hash, commit, retrieval metrics before and after on dev, judge status, kept or rejected, and why.

## Risks

- dev_v1 has 20 questions. Recall differences on 20 items are noisy, so only large gains count until dev reaches 40 or 65.
- Sonnet labels can share bias with the judge (both Claude). The owner sample is the check; disagreement above 15 per cent on the sample stops step 1.
- Retrieval wins on dev do not guarantee wins end to end.

## Alternatives considered

- Judge labels by the owner only: slower, but no model bias. Rejected as the default because it blocks step 1; kept as the fallback if the owner sample disagrees with Sonnet.
- Start with the end-to-end run: rejected, it costs money before the judge and retrieval are measured.
