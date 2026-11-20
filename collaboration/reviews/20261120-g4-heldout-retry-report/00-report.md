# G4 held-out 62 retry report (Amendment 2)

Date: 2026-11-20
Amendment: `collaboration/designs/20261120-rag-g4-heldout/03-implementation-handoff.md`
§Amendment 2 (owner-approved 2026-11-20): retry the 34 failed questions;
hard cap $0.80, stop at cumulative $0.70; health check first; stop at 3
consecutive 500s.
Branch: `g4-heldout-62-2026-11-20`. No merge, no deploy.

## Outcome: stopped at the ledger stop on the retry's first question; the retry produced no committed outcomes

1. **Health check passed.** One question (62-file index 26, the first of the
   34), full pipeline, all HTTP 200s, answered as a correct refusal. It cost
   **$0.517896** — a pathological ~1.4M-token cached prompt (a handful of
   questions in this set triggers prompt-size blowups; pass 1's average was
   ~$0.02/question, but the variance is extreme).
2. **Retry aborted at the ledger stop.** With $0.70 − $0.518 = $0.182104
   remaining, the retry's first agent call — index 26 again, same
   giant-prompt pathology — cost **$0.362940** in a single call and the
   ledger raised `BudgetExceededError` (`$0.362940 >= $0.182104`). **Zero
   HTTP 500s in the retry**; the 3-consecutive-500 stop never neared
   triggering. The CLI writes no artifacts on a budget abort, so the retry
   run itself produced no committed artifacts; the health-check run is
   preserved at `reports/sealed_v2_62_retry/health_check/` as spend
   evidence (documented deviation: the amendment named that folder for the
   34-run, which aborted empty).
3. **Hard-cap overshoot, stated plainly.** Retry-authority spend totals
   $0.517896 + $0.362940 = **$0.880836**, which exceeds the $0.80 hard cap.
   The meter prices a call and then raises; a single call larger than the
   remaining headroom jumps straight past the cap. The overshoot was caused
   by the index-26 question's ~0.4–0.5 MB-context cost occurring twice
   (health check + retry first position), not by scope creep.

## Spend accounting (all kimi-for-coding, cloud-equivalent, committed meters)

- Pass 1 (62 questions, 34 provider-500 failures): $0.526214
- Retry authority: health check $0.517896 + retry abort $0.362940 = **$0.880836**
- **G4 cumulative: $1.40705.** No Ollama, no other provider.

## Commits and hashes

- `acd5356` — `docs(01): sealed-v2 held-out retry subset (34) defined and hashed`
  (retry file sha256 `f805eadfba6f…`, cross-checked against the original
  run's format-failure rows; parent `616973ba…` re-verified)
- `d8696ad` — `feat(01): sealed-v2 held-out retry - ledger stop on first question`
  (health-check artifacts + gitignore whitelist)

## Counts and combined view

- 62-file state after the retry: 28 real outcomes from pass 1 (indices
  0–25, 36, 43) + index 26 answered by the health check (scratch, committed
  under the retry folder) + **33 questions still unfetched** (indices 27–35,
  37–42, 44–61). No committed outcome exists for the 33.
- **Combined 62 table (combined, retry for failed items only)** — best
  available view, with its limit stated: pass-1 verdicts on the 28 healthy
  indices, health-check verdict on 26, and "unfetched" for the 33:

| verdict | count | basis |
|---|---|---|
| correct | 37 + 1 = 38 | pass 1 (37 of 62) + health check (index 26) |
| unsupported-claim | 7 | pass 1 |
| empty-answer | 2 | pass 1 |
| format-failure (provider 500/timeout) | 33 | pass 1 (34) minus index 26, refetched by health check |
| unfetched (retry aborted) | 0 answered / 33 not-run | the retry produced no artifacts |

- **Questions still failing: 33** (plus the caveat that index 26's only
  outcome is the health-check scratch run).
- **Budget-terminated rows by index: none in pass 1's 62-run or the retry.**
  (The 58-run's two remain indices 23 and 35 of the 58-file, listed
  separately, never folded into unsupported.)
- **120 pooled: stays marked invalid** — 33 of 62 questions still have no
  committed outcome; `reports/sealed_v2_120_pooled/metrics.json` is
  unchanged (its counts and warning remain accurate).

## Gates (actual output)

- `uv run python scripts/check_headline_numbers.py` → `11 claims checked,
  0 finding(s)` / `OK`
- `uv run python scripts/check_docs.py` → `check-docs: OK`

## Deviations

1. Health-check artifacts committed under
   `reports/sealed_v2_62_retry/health_check/` — the amendment reserved the
   folder for the 34-run, which aborted with no artifacts; keeping the
   health evidence there documents the spend honestly.
2. The $0.80 hard cap was overshot to $0.880836 by the meter's post-pricing
   enforcement on a single oversized call (details above); nothing was run
   after the abort.
3. Index 26 was evaluated twice (health check + retry first position), at
   combined ~$0.88 — the amendment's fixed subset order puts the most
   expensive question first; no reordering was permitted.

## Owner decision this hands back

Fetching the remaining 33 questions needs a new cap sized for the
prompt-blowup reality: at least one more question near index 26's cost class
(~$0.4–0.5) plus ~32 average questions (~$0.02–0.05) suggests **≥ $1.00** of
fresh headroom, and the order guarantees the first question is the expensive
one. Alternatively, investigate the prompt-size blowup (some retrieved
contexts appear to stuff ~1.4M tokens) before spending again — that is a
code-level question outside this amendment's no-change rule.
