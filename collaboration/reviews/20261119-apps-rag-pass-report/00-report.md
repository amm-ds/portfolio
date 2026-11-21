# Apps and RAG pass report

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-apps-and-rag-pass/03-implementation-handoff.md`
Branch: `apps-rag-pass-2026-11-19` from `main` (3ac47bd) — pushed with
upstream, NOT merged, no deploy. Hosted spend: **$0.3944 total** (R2 only;
cap $3 combined, stop $2.50 — R3 held, see below).

## Step rows

| Step | Status | Files | Gates actually run |
|---|---|---|---|
| 1 audit | done; committed `2f8a0af` | `collaboration/reviews/20261119-apps-rag-pass-audit/00-audit.md` | coverage via ephemeral pytest-cov (ac 89.85%, di 84.59%, suites exit 0); ruff+mypy clean both apps (0 findings); no audit tool configured (recorded) |
| 2 real bugs | none (empty commit `31a55e9`) | — | audit found zero lint findings |
| 3 rate limiting | done; `3b5a7f9` | both apps' `rate_limit.py`, `config.py`, `state.py`, `app.py` (header forwarding), routes, tests, READMEs | both suites exit 0; ruff/format/mypy clean; 429 + Retry-After, per-key isolation, window reset tested |
| 4 health/error shape | done; `56da0e8` | 404 status handlers (both apps), `test_error_contract.py` ×2 | suites exit 0; ruff/format/mypy clean. Compose: DI targets /ready ✓; agent-chat api has no healthcheck — deployment files out of scope, recorded |
| 5 coverage floor | **held**; `23b2aa9` + OPEN_QUESTIONS.md | — | floor requires pytest-cov = new dependency (0 coverage tooling in either uv.lock) → held with measured floors recorded (89.8 / 84.5) |
| 6 R4 + R5 | done; `233e083` | `scripts/retrieval_baseline.py`, `scripts/error_budget.py` + new report dirs (+ 2 gitignore negations) | project-01 suite exit 0; ruff/format/mypy clean; headline + docs OK |
| 7 R2 warrant check | done; `2a6e74d` — **spend $0.3944** | `scripts/warrant_check.py` + `reports/warrant_check/` (+ negation) | suite/ruff/mypy/headline/docs green |
| 8 R3 sealed v2 | **set committed `f3551b3`; run HELD**; `d9f6bdd` | `data/golden_sealed_v2.json` (+sha256 manifest), `--heldout-file` CLI flag, validation helper | suite/ruff/mypy green; run held: cost > cap (below) |

## Numbers (each with its source file)

- **Coverage floors (measured)**: agent-chat 89.85% = 1744 stmts / 177
  missed → floor **89.8**; document-intelligence 84.59% = 1947/300 →
  **84.5** (audit §2; held pending the pytest-cov decision).
- **R4** (`projects/01-rag-agent/reports/retrieval_baseline/metrics.json`,
  n=42 answerable sealed questions, recomputed and verified against the
  committed `sealed_retrieval.json` arms): dense recall@5 **0.9762**
  [0.8768, 0.9958]; BM25 recall@5 **0.9524** [0.8421, 0.9868]; recall@10
  1.0000 / 0.9762; MRR@5 0.9034 / 0.8829. BM25 is within a few points of
  dense, far inside both intervals.
- **R5** (`projects/01-rag-agent/reports/error_budget/metrics.json`, sealed
  held-out run, committed metrics only): cost **$0.000906/query**
  (cloud-equivalent); latency p50 **24.44 s**, p95 **126.81 s**
  (detail.heldout.ops); unsupported-claim rate **9/55 = 0.1636** Wilson 95%
  **[0.0873, 0.2712]** (per-question heldout traces).
- **R2** (`projects/01-rag-agent/reports/warrant_check/metrics.json`): 219
  of 247 accepted claims judged (28 excluded: evidence span not locatable
  offline, counted not guessed); verdicts supports 179 / **overstates 27** /
  does-not-support 13. Overstatement rate **27/219 = 0.1233** Wilson 95%
  **[0.0861, 0.1734]** vs the committed binary unsupported 11/258 = 0.0426
  [0.0240, 0.0747]. Spend **$0.3944** (147,149 in / 61,805 out tokens at
  $1/$4 per Mtok).
- **R3 economics** (hold decision): committed heldout meter $1.950667 for
  55 questions ($0.035/question) → 120 questions ≈ **$4.25**; R2 + R3 ≈
  $4.65 ≫ $3 cap / $2.50 stop → held per the handoff. Sealed-v2 sha256:
  `616973ba390fdc1f8c9bf0b53fcf8e1b9bd24f5e93b563184bbc2ca9f8ce54e2`
  (manifest: `data/golden_sealed_v2.sha256.json`).

## Hosted spend

R2: **$0.3944** (cloud-equivalent at the reference card; membership key,
not billed). R3: **$0.00 — not run** (held). Total: **$0.3944** of $3.00.

## Commits

`2f8a0af` audit · `31a55e9` step 2 no-op · `3b5a7f9` rate limiting ·
`56da0e8` error contract · `23b2aa9` step-5 hold · `233e083` R4+R5 ·
`2a6e74d` R2 · `f3551b3` sealed v2 + flag · `d9f6bdd` R3 hold.
Push: new branch, upstream set.

## Open questions (owner decisions)

1. `OPEN_QUESTIONS.md`: pytest-cov dev dependency for the coverage floors
   (89.8 / 84.5 measured, ready to wire).
2. `OPEN_QUESTIONS.md`: R3 needs ≈$4.5 total cap (or an approved reduced
   60-question pass ≈$2.1); set + mechanics are committed and ready.
3. R2's result is for the owner: ~1 accepted claim in 8 overstates its
   citation — the verify-on copy states the measured miss rates and was not
   changed here.
