# Implementation handoff: G4, held-out 62 on the unchanged production configuration

Date: 2026-11-20
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): hosted cap $1.30, stop at cumulative $1.20, `kimi-for-coding` only. Nothing else approved.
Source: `collaboration/designs/20261120-rag-finish-plan/00-plan.md` (replaces Phase 2 if the owner approves); `collaboration/designs/20261119-r3-sealed-v2-58/03-implementation-handoff.md` (the 58-question run this extends).

## Objective

Run the 62 sealed_v2 questions that were not in the 58-question pass, on the unchanged production configuration, and save the full per-question answers and claim text. The 58 run kept only claim counts, so Phase 1 (human audit) and any failure analysis cannot be done from committed artifacts. This run fixes that, and gives a 120-question result with one configuration.

## Facts already checked (2026-11-20)

- `data/golden_sealed_v2.json`: 120 items.
- `data/golden_sealed_v2_58.json`: 58 items (even zero-based indices 0..114).
- Complement (62 items): 32 single_hop, 12 multi_hop, 18 unanswerable. Answerable 44.
- The 58-question traces (`reports/sealed_v2/question_traces_heldout.json`) have no answer text and no claim text. Only `claim_states` counts. Two answerable rows (indices 23 and 35) were `budget-terminated` at the per-answer 4,000,000-token limit.
- Prior 58-question spend: $1.034388 on the kimi-for-coding meter (cloud-equivalent estimate on a membership key, not a billed amount).

## Standing rules

- Branch `g4-heldout-62-2026-11-20` from `main`. Commit with trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. No merge, no deploy, no git mutation beyond this branch.
- Hosted calls: `kimi-for-coding` only, the same provider and model as the 58 run. No other hosted model.
- Do not change the production configuration: `params.yaml`, prompts, verify loop, thresholds, judge. Run the code as committed.
- Do not edit `golden_sealed_v2.json`, `golden_sealed_v2_58.json`, any committed report, or copy.
- No new dependency, no download.

## Steps

1. Create `projects/01-rag-agent/data/golden_sealed_v2_62.json` as the complement of `golden_sealed_v2_58.json` within `golden_sealed_v2.json`, in original order. Assert: 62 items, disjoint from the 58, union equals the 120, category mix 32/12/18. Record sha256 of the new file and of its source. Commit: `docs(01): sealed-v2 held-out complement (62) defined and hashed`.
2. Record the git hash of the code path and the parent sha256 of `golden_sealed_v2.json` (`616973ba390fdc1f8c9bf0b53fcf8e1b9bd24f5e93b563184bbc2ca9f8ce54e2`). Stop if it differs.
3. Run the sealed pass on the 62-item file with the same CLI form as the 58 run (see `reports/sealed_v2/report.md` header and the 58 handoff for the exact invocation), changing only `--heldout-file` to the 62 file and `--reports-dir` to a NEW folder `reports/sealed_v2_62/`. Do not write to `reports/sealed_v2/`.
4. Save per-question answers and claim text in the run's trace output. If the existing trace schema does not hold them, stop and report the gap; do not add answer capture by editing production code without owner approval.
5. Confirm the run's spend from the meter. Stop at the cumulative cap in the Budget section.
6. Write `reports/sealed_v2_62/metrics.json` and `report.md`, using the same metric definitions as the 58 run: unsupported-claim rate over answerable questions with Wilson 95%; false abstention over answerable questions; unanswerable abstention; faithfulness; answer relevance; context recall; latency p50 and p95; budget-terminated count.
7. Pool with the 58 run, then compute, for all 120 questions: answerable count, unsupported count and rate with Wilson 95%, false abstention with Wilson 95%, budget-terminated count (listed separately, not folded into unsupported). Write `reports/sealed_v2_120_pooled/metrics.json` with the input file hashes and the two run folders named.
8. Report the 26% headline's denominator explicitly in the report: all questions and answerable-only, both with counts.
9. Write `collaboration/reviews/20261120-g4-heldout-report/00-report.md`: commit hashes, file hashes, Ollama not used (hosted only), spend from the meter, all counts, pooled table, budget-terminated rows by index, and any deviation from this handoff.

## Gates

- `uv run pytest -q projects/01-rag-agent`
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`

Report actual output. Do not claim a gate passed unless it ran. The RAG suite coverage gate was failing before (78.19% against 80%); report it separately and do not change the threshold.

## Budget

- Expected spend: about $1.10 (58-question run $1.034; 62 items with a similar answerable mix).
- Approved hard cap: $1.30. Stop at cumulative $1.20 (owner, 2026-11-20).
- Stop if the meter reaches the stop figure. Report completed items and the rest.

## Stop conditions

- Any hosted call other than `kimi-for-coding`: stop.
- Production configuration or committed files would change: stop and report.
- Answer or claim text not retained by the trace output: stop and report before spending the full run; do not patch production code.
- Parent hash mismatch: stop.

## Decisions this handoff does not make

- Whether the 120-question pooled figure replaces the 58-question headline in copy. That is an owner decision after the report.
- Phase 1 labels and Phase 2 candidate. These follow from this run's saved answers.
