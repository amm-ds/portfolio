# Prompt-size investigation: why some sealed-v2 questions send ~1.4M-token prompts

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-prompt-size-investigation/03-implementation-handoff.md`
(approved read-only; $0 hosted; no pipeline runs; no src/params/prompts/report/copy edits)
Branch: `prompt-size-investigation-2026-11-20` from `g4-heldout-62-2026-11-20` (`522ca2b`).
No merge, no deploy. Code-path trace delegated read-only to an explore subagent;
every load-bearing reference re-verified against the tree by the author.

## 1. Per-question token data: availability statement

**Per-question input/output token counts are NOT committed anywhere.**
`QuestionTrace` (`src/rag_agent/reporting.py:61-87`) records no token or
tool-call fields. The meter (`src/rag_agent/metering.py:85-118`) stores
per-phase **run-cumulative** totals, and its `agent` phase records one entry
per *question* whose `input_tokens` are the sum of input tokens across all
model turns of that answer (pydantic-ai `RunUsage` accumulates per run;
metering.py:58-70). Per-request usage is logged to the console only
(`libs/portfolio-core/src/portfolio_core/llm_budget.py:209-216`), never
persisted per question.

What the committed meters do show (detail.heldout.meter of each run):

| run | agent phase (questions / input tok / cached / output tok) | judge | verify |
|---|---|---|---|
| 58-run (`reports/sealed_v2/metrics.json`) | 56 rec, 1,580,273 in, 1,376,000 cached, 42,054 out | 112 rec, 68k in | 52 rec, 42k in |
| 62 pass 1 (`reports/sealed_v2_62/metrics.json`) | 28 rec, 805,614 in, 696,576 cached, 22,996 out | 54 rec, 34k in | 26 rec, 22k in |
| **62[26] health check** (`reports/sealed_v2_62_retry/health_check/metrics.json`) | **1 rec, 1,501,414 in, 1,435,136 cached, 4,128 out** | 2 rec, 1.4k in | 0 rec (skipped) |
| final 33 (`reports/sealed_v2_62_retry/metrics.json`) | 33 rec, 3,053,528 in, 2,822,937 cached, 30,887 out | 66 rec, 40k in | 32 rec, 31k in |

Derived per-question figures: 62[26] ≈ **1.50M input tokens in one answer**
(~1.35M of them cache hits, i.e. re-sent transcript), with only ~4.1k output
tokens — dozens of tiny turns. The 58-run average is ~28k input per answered
question. The final-33 run contains two further questions in the ~$0.5 spend
class (≈0.8–1M tokens each) at ≈19:47 and ≈19:55; the committed artifacts
cannot map meter rows to question indices, so those two are not nameable
from evidence.

## 2. The large cases and a typical row

| case | file/index | category / behavior | evidence |
|---|---|---|---|
| 62[26] | 62-file | unanswerable / abstain | 1.50M input, 4.1k output, verify skipped, correct refusal (`health_check/question_traces_heldout.json`) |
| 58[23] | 58-file | single_hop / answer | `UsageLimitExceeded: total_tokens_limit of 4000000 (total=4,005,788)`, `output_retries: 0` (`reports/sealed_v2/question_traces_heldout.json:539`) |
| 58[35] | 58-file | single_hop / answer | same cap, total=4,010,952 (`:807`) |
| typical | 58-run | answerable | median `output_retries` 0, median 2 surviving claims (max 5); ~28k input per answer |

## 3. Context path, hop by hop (verified file:line)

```
question
 ├─ offline retrieval for gate/judge only (evaluate.py:604-614; top_k=3, params.yaml:67)
 │
 ├─ AGENT LOOP  answer_with_output_retries → agent.run_sync   evaluate.py:181-186
 │   fresh run per attempt; per attempt:
 │   • system prompt ≈450 tok (agent.py:30-57) + JSON output schema (agent.py:74-85)
 │   • turn 1..N: EVERY model request re-sends the full accumulated transcript —
 │     no history trim (no history_processors / max_history_messages in agent.py:79-85)
 │   • search_documents(query, top_k) → list[Citation]      agent.py:87-92 → index.py:232
 │       model-chosen top_k, NO validation; excerpt 240 chars/citation (index.py:247-250,
 │       config.py:165); k > corpus size returns every chunk
 │   • read_excerpt(chunk_id) → full chunk text (~200 words) agent.py:94-100
 │   • UsageLimits(request_limit=400, total_tokens_limit=4M) llm_budget.py:275-278,
 │     defaults config.py:36-37 — the ONLY per-answer bounds; no max_turns / tool-call cap
 │
 ├─ VERIFY LOOP  verify.py:434-450 (full cited chunks, bounded ≤3k tok),
 │   1 batch judge + ≤2 repairs + ≤2 reverifies (verify.py:536,587,667,694) — all
 │   fresh single-turn runs; bounded by max_repair_calls=2 (params.yaml:76)
 │
 └─ RUBRIC JUDGE 2 fresh single-turn calls (evaluate.py:689-692; judge.py:53),
     context = 3×240 chars — bounded. RAGAS off in held-out runs.
```

## 4. Ranked hypotheses

**H1 — Multi-turn tool loop × full-transcript re-send (near-quadratic growth).
Best fit; mechanism confirmed, magnitude inferred.**
For: `RunUsage.input_tokens` sums across requests, each re-sending the whole
transcript; the project documents this exact pathology (schemas.py:71-75);
62[26]'s signature (1.50M in / 4.1k out / 93% cached / verify skipped) fits
~35–40 tiny turns re-sending a growing transcript; 58[23] and 58[35] hit the
4M cumulative cap inside one attempt with `output_retries: 0`.
Against: no committed per-turn counts; the 1.4–1.5M is a **run-cumulative**
figure — the largest single HTTP prompt under H1 is ~tens of k tokens, not
1.4M. Settling check (read-only): none exists — needs a local Ollama
reproduction or one instrumented hosted run (open question, §7).

**H2 — Model requests a giant `top_k`; one `search_documents` call returns
the whole corpus (~360k+ tokens in one tool result). Amplifier; only path to
a genuinely giant single prompt.**
For: `top_k` is model-controlled and unvalidated (agent.py:89 → index.py:232
`k = top_k or self.config.top_k`); `candidates[:k]` returns every chunk when
k exceeds the corpus; ~6k chunks × 240-char excerpt ≈ 360k tokens, re-sent on
every later turn — a few such calls reproduce 1.4M quickly.
Against: no committed evidence of a huge tool result; 62[26]'s tiny output
fits many-small-turns equally. Settling check: same open-data caveat as H1;
also the biggest single-call cost would show as a spend jump mid-question,
which the console-only logs don't persist.

**H3 — Output retries or verify repairs re-appending accumulated text.
Ruled out as the cause.**
Each retry restarts `agent.run_sync` fresh with new `UsageLimits`
(evaluate.py:151-158, 181-186); verify/judge calls are fresh single-turn
runs with small bounded prompts; both 4M-cap rows show `output_retries: 0`.
At most it multiplies an H1 blowup by ≤3 attempts.

## 5. Verdict

**Defect — an unbounded interaction, not expected behaviour.** The per-answer
budget has no turn/tool-call cap and no per-request input cap; the only
limits are request_limit=400 and a 4M total-token ceiling, both far above
what a runaway tool loop needs to stall (evidence: two rows aborted at 4.0M,
one answer at 1.5M before refusing). The design's own history acknowledges
the loop pathology (schemas.py:71-75). The cost is bounded by the caps, but
"the model loops until a 4M-token abort" is a failure mode for production
answers (latency, cost, and — in the local-provider path — *no limit at
all*: `budget_limits()` returns `None` when not hosted, llm_budget.py:270-271).
A fix design (e.g., max tool turns, per-request input cap, transcript
trimming, or a validated `top_k` bound) belongs in a separate handoff; none
is implemented here.

## 6. Are the 15/58 and 28/120 numbers affected?

**Not inflated; slightly understated-unknown.** The budget-terminated rows
(58-file 23, 35) are excluded from the unsupported counts and listed
separately by definition, so the 26% (15/58) and 28/120 figures are computed
only over questions that completed — the blowups did not manufacture
unsupported-claim verdicts. But two answerable questions (58-file 23, 35)
produced **no verdict at all**, so each rate silently misses whatever those
questions would have contributed; the direction of the bias is unknown (a
stalled single_hop question could as easily have become `correct` as
`unsupported-claim`). 62[26] completed (a correct refusal) and is counted.
The retry spend overrun was a measurement-cost issue only; it did not touch
any verdict.

## 7. Open questions for the owner (would need a hosted or instrumented run)

1. H1 vs H2 split: per-request/per-turn token and tool-call counts for
   62[26] and 58[23]/[35] — one instrumented run (or local Ollama
   reproduction) with per-call logging settles it. Read-only artifacts
   cannot.
2. Which specific questions in the final-33 run were the two ~$0.5 giants
   (≈19:47 and ≈19:55) — recoverable only from a run with per-question meter
   persistence.

## 8. Gates

No gates required for this read-only phase (no code changes). Checks run:
the meter/trace extractions and file:line spot-verifications above (outputs
quoted inline).
