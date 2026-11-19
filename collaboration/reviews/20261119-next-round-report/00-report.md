# Next-round report: Q4a, RAG copy, DI expanded sample, Q4b

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-next-round/03-implementation-handoff.md`
(items 1, 3, 4 + the approved item-2 copy change; Q3b/Q3c/other Q4 not run)
Branch: `next-round-2026-11-19` from `main` (23816fe) — pushed with upstream,
not merged, not deployed. Hosted spend total: **$0.049502** (item 3 only,
cloud-equivalent at the $1.00/$4.00 per-Mtok reference card; cap $3, stop
rule $2.50 — nowhere near).

## Item rows

| Item | Status | Files | Gates actually run |
|---|---|---|---|
| 1 — Q4a uplift single protocol (10) | done; honest negative | new `src/uplift_experimentation/single_protocol.py`, `cli.py` (+command), `reports/single_protocol/{metrics.json,report.md}` | project-10 pytest exit 0 (69 tests); ruff check/format clean; mypy 15 files clean; headline-numbers OK (11 claims, 0 findings) |
| 2 — RAG verify-on copy (01) | done; no hosted calls | `story.yaml`, `README.md`, `docs/projects/01-rag-agent.md` | lint 0 errors/0 warnings; check-docs OK; short-copy 39 surfaces OK; storyShort current (no regen); headline-numbers OK. Web gates not run (storyShort.ts unchanged) |
| 3 — DI expanded live sample | done; spend $0.049502 | new `fixtures_expanded.py`, `scripts/generate_expanded_fixtures.py`, `scripts/compare_expanded_sample.py`, `fixtures/expanded/` (7 PDFs), `evaluations/references-expanded-2026-11-19.json`, `reports/expanded-2026-11-19/{live-metrics.json,comparison.json,comparison.md}` | `uv run pytest -q apps/document-intelligence` exit 0; ruff check/format on new files clean; check-docs OK |
| 4 — Q4b risk-coverage (04) | done | new `src/nlp_classification/risk_coverage.py`, `cli.py` (+command), `reports/risk_coverage/{metrics.json,report.md}` | project-04 pytest exit 0; ruff check/format clean; mypy 14 files clean; headline-numbers OK |

Commits: `97bd4f8` (Q4a) · `0622f92` (RAG copy) · `3249606` (Q4b) ·
`0a577aa` (DI expanded). Push: new branch, upstream set.

## Numbers (each with its source file)

**Item 1** (`projects/10-uplift-experimentation/reports/single_protocol/metrics.json`,
n = 42,613 rows, committed folds seed 42 / 5 folds, outcome conversion;
Qini area = AUUC, unnormalised — area between the incremental-conversions
curve and the random line; paired row bootstrap 2000, seed 42):

- causal_forest (hand-rolled DR-learner sklearn forest, cross-fitted): **−3.53 [−16.21, 9.70]**
- t_learner (= two-model approach; same estimator family, one committed OOF column): **12.03 [−0.01, 24.18]** — matches the committed headline Qini 12.0252 exactly (fold-identity check: recomputed T-learner column == committed scores.parquet)
- x_learner: **5.90 [−6.10, 17.90]**
- DR policy value by budget (with intervals) per learner in metrics.json.
- Interpretation: the hand-rolled causal forest does not beat the plain
  T-learner under the single protocol; no learner's interval excludes the
  others.

**Item 2** (numbers from
`projects/01-rag-agent/reports/judge_calibration_report.json`, quoted in the
story background/training/results, the 01 README, and the docs project page):
local qwen2.5:3b accepts **0.4433** of unsupported claims, Wilson 95%
**[0.3752, 0.5136]**, kappa **0.5464**; hosted qwen3:4b strict
unsupported-only **0.3966 [0.3269, 0.4707]**, kappa **0.6052 [0.5262,
0.6831]**. The non-reconciling committed hosted aggregate (0.4536) is not
quoted anywhere. Roadmap card now reads "Answers face a three-judge citation
check." with detail "…judges miss 0.44 of unsupported." Headline numbers,
sealed-set results, and $0.000906/query unchanged.

**Item 3** (`apps/document-intelligence/reports/expanded-2026-11-19/`):

- Hosted spend **$0.049502** cloud-equivalent ($1.00/Mtok in, $4.00/Mtok out
  reference card; 1,294 input / 12,052 output estimated tokens). Cap $3, stop
  $2.50 — not approached. Provider: kimi-for-coding only.
- Entity F1, original 7-document subset: **0.7778 [0.5405, 0.9254]** (n=8
  reference pages) vs expanded 14-document set: **0.7292 [0.5714, 0.8491]**
  (n=15 pages) — pooled per-page counts, bootstrap over pages, seed 42
  (`comparison.json`).
- Committed headline entity F1 0.677 (live-metrics.json, 2026-11-08) lies
  inside the re-measured interval → no stop condition.
- Disclosed: one provider error (`protocol`, UnexpectedModelBehavior on one
  page; page_failure_rate 0.067). No card or article copy changed.

**Item 4** (`projects/04-nlp-classification/reports/risk_coverage/metrics.json`,
n = 1,000 fresh holdout, max-softmax confidence; identity check recomputed
fresh macro-F1 0.9529432 == committed):

- **AURC 0.0068 [0.0037, 0.0106]** (area under risk-vs-coverage; paired row
  bootstrap 2000, seed 42).
- Risk at coverage: 1.00 → 0.0470 · 0.90 → 0.0178 · 0.75 → 0.0093 ·
  0.50 → 0.0020 · 0.25 → 0.0000.

## Notes and open questions

- Item 1 deliberately used no new dependency: DESIGN.md defers grf/econml
  ("heavyweight deps") and the source design says "no new dependencies", so
  the causal forest is a hand-rolled DR-learner forest on sklearn, labelled
  exactly as such. DESIGN.md's "Deferred" row is now factually stale (a
  hand-rolled variant ran) — left untouched per the no-copy-changes rule;
  owner may want one line updated.
- Item 1's "two-model learner": the two-model approach and the T-learner are
  the same estimator family in the uplift literature; one committed OOF
  column carries both labels (stated in the report and metrics.json).
- Item 3's sample is still small (15 reference pages); the intervals remain
  wide — the expansion supports the smoke-level claim, not more. The
  stop condition (original headline moved beyond interval) did not trigger.
- `collaboration/designs/20261119-next-steps/` remains untracked (the source
  design; out of the handoff's commit scope).
- Not run, per instructions: Q3b, Q3c, Q4c–Q4h. No deploys; main untouched.
