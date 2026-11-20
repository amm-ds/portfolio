# G4 held-out 62 report — STOP before spend (trace schema gap)

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-rag-g4-heldout/03-implementation-handoff.md`
(approved cap $1.30, stop at cumulative $1.20, kimi-for-coding only)
Branch: `g4-heldout-62-2026-11-20` from `verifier-reconciliation-2026-11-20`
(head `e7a4880`). No merge, no deploy.

## Outcome

**Stopped before any hosted spend, per the handoff's own step 4 and stop
conditions. Meter spend: $0.00. No evaluation ran; no `reports/sealed_v2_62/`
folder was created; no production configuration, committed golden file,
committed report, or copy was touched.** The one approved prep step (define
and hash the 62-question complement) was completed so an approved
continuation can start immediately.

## Why the stop: the trace schema holds no answers and no claim text

Handoff step 4 requires per-question answers and claim text in the run's
trace output, and forbids adding capture by editing production code without
owner approval. The committed schema, verified on this exact code path
(the same commit the 58-question run used):

`src/rag_agent/reporting.py:60-83` — `QuestionTrace` fields, verbatim:

```
question, category, expected_behavior, top_rank, retrieved_relevant,
cited_relevant, faithfulness, abstained, format_ok, output_retries, error,
gate_coverage, gate_max_similarity, evidence_score, n_surviving_claims,
budget_terminated, gate_refused, claim_states
```

`src/rag_agent/evaluate.py:693-711` constructs exactly these fields; the
summary text exists in memory (`summary = output.summary`) but is written
only into the in-memory `RagasRow` sample (not committed; not produced
without `--ragas`), and claim text is never recorded — only
`n_surviving_claims` and the `claim_states` counts. `write_question_traces`
serializes what it is given. Conclusion: with the code as committed, an
approved run would reproduce the 58-question run's gap — no answer text, no
claim text — making the handoff's stated purpose (Phase 1 human audit and
failure analysis from committed artifacts) impossible. This is the handoff's
own stop condition; stopping is following the handoff, not deviating from
it.

## Documented deviation: branch base

The handoff says branch from `main`. Verified impossible to satisfy together
with "unchanged production configuration" and "pool with the 58 run":

- `origin/main` (tip `3ac47bd`) has **no** `data/golden_sealed_v2.json`,
  **no** `data/golden_sealed_v2_58.json`, and **no** `reports/sealed_v2/`
  (`git ls-tree origin/main` checked 2026-11-20).
- `src/rag_agent/cli.py` on main differs from the 58-run code by 72 lines
  (`git diff origin/main..apps-rag-pass-2026-11-19`); the 58 run
  (`557ad6b`) exists only on the apps-rag-pass line.

Owner decision (2026-11-20): branch from `verifier-reconciliation-2026-11-20`
(`e7a4880`), the tip that contains the 58 run, its reports, and the
identical code path. Deviation recorded per handoff step 9.

## Hashes and commits

- Prep commit: `20814ff` — `docs(01): sealed-v2 held-out complement (62)
  defined and hashed`
- Code-path git hash: `e7a4880b63228ee7f19ff17dc1ccc471a730598a`
- Parent `data/golden_sealed_v2.json` sha256:
  `616973ba390fdc1f8c9bf0b53fcf8e1b9bd24f5e93b563184bbc2ca9f8ce54e2`
  — **matches the handoff's recorded value; step-2 stop condition clear.**
- New `data/golden_sealed_v2_62.json` sha256:
  `a57355f5d853bd86512d2fec816a950fd25a15aee1e540d414871f0c4836b4f0`
- Complement verified: 62 items, disjoint from the 58, union equals the 120;
  category mix 32 single_hop / 12 multi_hop / 18 unanswerable (44
  answerable). Original order preserved.

## Gates (actual output)

- `uv run pytest -q projects/01-rag-agent` → **204 passed, 0 failed**; exit 1
  solely from the pre-existing libs coverage gate (`Required test coverage of
  80.0 not reached. Total coverage: 78.19%`) — reported separately per the
  handoff; threshold untouched.
- `uv run python scripts/check_headline_numbers.py` → `11 claims checked,
  0 finding(s)` / `OK`
- `uv run python scripts/check_docs.py` → `check-docs: OK`

## Context restated for the approved continuation

- 58-question run budget-terminated rows by index: **23 and 35**
  (answerable rows terminated at the per-answer 4,000,000-token limit;
  recorded in `reports/sealed_v2/metrics.json` and the r3-sealed-v2-58
  report). This run produced none (it did not run).
- The 26% headline, denominator both ways: **15/58 = 0.2586** (Wilson 95%
  [0.1635, 0.3838]) over **all 58 questions**; over **answerable-only (48)**
  the same 15 unsupported outcomes are **15/48 = 0.3125**. The public 26%
  headline uses the all-questions denominator.
- Prior 58-question spend (for the record): $1.034388 cloud-equivalent on
  the kimi-for-coding meter. **This pass added $0.00.**

## Zero-hosted-calls and no-Ollama statement

No hosted calls were made (kimi-for-coding or otherwise); no local Ollama
calls were made. The only actions were git operations, file hashing, the
free gates above, and reading committed artifacts.

## What an approved continuation needs (owner decisions, not made here)

1. Approve a minimal trace extension in advance — e.g. optional
   `answer: str | None` and `claims: list[str] | None` on `QuestionTrace`,
   populated from `output.summary` and the verify report — as a separate,
   reviewed change to production code; OR
2. Accept count-only traces and restate the handoff's objective without
   per-claim text (Phase 1 audit would then need a separate capture path).

With either decision, this branch's committed 62-file and hashes let the run
proceed immediately under the same caps ($1.30 hard, $1.20 stop).
