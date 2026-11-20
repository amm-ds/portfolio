# G4 held-out 62 report

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-rag-g4-heldout/03-implementation-handoff.md`
+ Amendment (owner-approved 2026-11-20): minimal trace extension.
Budget: kimi-for-coding only, hard cap $1.30, stop at cumulative $1.20.
Branch: `g4-heldout-62-2026-11-20`. No merge, no deploy.

## Headline: run completed under budget, but a provider 500 storm makes it a degraded measurement

The 62-question pass ran to completion on the unchanged production
configuration (+ the approved trace amendment) for **$0.526214
cloud-equivalent** (ledger budget $1.20; stop and hard cap never reached).
However, the kimi-for-coding endpoint began returning HTTP 500 at trace
index 26 and never recovered (brief islands at indices 36 and 43): **34 of
62 traces are `format-failure`** (33 `ModelHTTPError 500`, 1 request
timeout). Only **28 of 62 questions produced real outcomes**. The numbers
below are committed exactly as measured; the pooled 120 figures are the
handoff's mechanical pool but are **not a valid 120-question configuration
measurement**. A clean re-run needs a fresh cap decision (~$1.10 expected;
remaining stop headroom $0.6738 does not cover it).

## Commits and hashes

- `20814ff` — `docs(01): sealed-v2 held-out complement (62) defined and hashed`
- `f43e2c9` — `feat(01): sealed-v2 trace carries answer and claim text (optional, default none)` (amendment, committed separately per the amendment)
- `f83556c` — gitignore whitelist for the two new report folders
- `99e4530` — `feat(01): sealed-v2 held-out 62 pass - degraded by provider 500 storm`
- `67e695d` — `feat(01): sealed-v2 120 pooled metrics with validity warning`
- Code-path hash at run time: `f83556c`; parent `golden_sealed_v2.json`
  sha256 verified before the run: `616973ba…ce54e2` (matches the handoff).
- Input hashes: `_58` `266d2ef3…20fb17`; `_62` `a57355f5…36b4f0`.

## Amendment gates (actual output, run before the hosted pass)

- `uv run pytest -q projects/01-rag-agent` → **207 passed, 0 failed**; the
  command exits 1 solely on the known pre-existing libs coverage gate
  (`Required test coverage of 80.0 not reached. Total coverage: 78.19%`) —
  reported separately per the handoff; threshold untouched.
- `check_headline_numbers.py` → `11 claims checked, 0 finding(s)` / `OK`
- `check_docs.py` → `check-docs: OK`

## The run (handoff steps 5–6)

- Invocation: `uv run python -m rag_agent.cli evaluate --heldout
  --heldout-file data/golden_sealed_v2_62.json --reports-dir
  reports/sealed_v2_62` from `projects/01-rag-agent`, root `.env` sourced,
  `LLM_COST_LIMIT_USD=1.20` exported (process env only). `reports/sealed_v2/`
  untouched; no committed golden file, report, or copy edited.
- Meter: `ledger_spend_usd` **0.526214**, `budget_usd` 1.20, model
  kimi-for-coding, 108 calls. **Ollama was not used (hosted only).**
- Verdicts (62 traces): correct 19, unsupported-claim 7, empty-answer 2,
  **format-failure 34** (all provider errors; first at index 26).
- **Budget-terminated rows by index: none in this run.** (The 58-question
  run's two remain indices **23 and 35** of the 58-file, listed separately,
  never folded into unsupported.)
- Unsupported-claim rate, **26%-style denominator stated both ways**:
  - all questions: **7/62 = 0.1129**, Wilson 95% [0.0558, 0.2152];
  - answerable-only (44): **7/44 = 0.1591**, Wilson 95% [0.0793, 0.2937].
  - For the record, the existing 26% headline is **15/58 = 0.2586** over all
    58 vs **15/48 = 0.3125** over answerable-only.
- Abstention: refusal accuracy 0.2778 (5/18 — depressed by the failure
  storm consuming unanswerable rows); false abstention 0.0455 (2/44).
- Quality (answered rows): faithfulness 0.59, answer relevance 0.6265,
  context recall 1.0. Latency p50 10.03 s, p95 132.33 s.

## Trace amendment verified (handoff step 4)

`reports/sealed_v2_62/question_traces_heldout.json` carries `answer` on the
28 answered rows and `claims` as `{claim, evidence_span, label, state}` on
the 23 rows with verify reports — the Phase 1 audit material the 58 run
lacked. Failure rows keep the pre-amendment schema exactly (keys omitted).

## Pooled 120 (handoff step 7) — with the validity warning

From `reports/sealed_v2_120_pooled/metrics.json`:

- answerable 92; unsupported **22/120 = 0.1833**, Wilson [0.1243, 0.2620]
  over all questions; 22/92 = 0.2391 over answerable-only.
- False abstention **6/92 = 0.0652** [0.0302, 0.1351].
- Budget-terminated: **2** (58-file indices 23 and 35; 62-file none) —
  listed separately, not folded into unsupported.

**Validity warning (also committed in the file):** the pool mixes 58 healthy
rows with 28 healthy + 34 provider-error rows; it must not be quoted as the
120-question configuration result. A capped re-run is the owner decision this
hands back.

## Deviations

1. Branch based on `verifier-reconciliation-2026-11-20`, not `main` — main
   lacks the sealed-v2 assets and the 58-run code path (documented in the
   stop-and-gap report, owner-approved).
2. The run's outcome (provider 500 storm) is reported as-is per the
   stop conditions — no stop condition fired mid-run (all calls were
   kimi-for-coding; caps untouched; parent hash matched; trace capture
   worked), and the handoff specifies completing and reporting rather than
   re-running.

## Zero-extra-spend statement

Hosted spend in this pass: **$0.526214 cloud-equivalent**, kimi-for-coding
only, from the committed meter. No Ollama, no other provider, no re-run.
