# Execution report: Q1, Q1b, Q2, Q3a, Q5

Date: 2026-11-19
Plan: `collaboration/designs/20261119-execution-plan-kimi/00-plan.md`
(Q1, Q1b, Q2, Q3a, Q5 approved; Q3b/Q3c/Q4 not run)
Hosted spend: **$0.00** (no hosted model calls; Q3b pending owner approval).
No git mutations, no deploys, no `.env`/permission/config changes.
Open questions: `collaboration/designs/20261119-execution-plan-kimi/OPEN_QUESTIONS.md`
(Q5 stop only).

## Item rows

| Item | Status | Files changed | Gates actually run |
|---|---|---|---|
| Q1 copy/roadmap fixes | done | 9 `story.yaml` (02, 03, 04, 06, 09, 10, 11, 12, 13), `README.md`, `docs/projects/index.md`, `docs/projects/09-agentic-workflows.md`, regenerated `storyShort.ts` | lint_story_language (0 err/1 soft warn), check_docs OK, check_short_copy OK, gen_story_short --check OK, check_headline_numbers OK (11 claims, 0 findings), web npm test 753 pass + lint + build |
| Q1b figure regen (10) | done (writer fix + regen) | `src/uplift_experimentation/evaluate.py` (annotation grid fix), `reports/figures/profit_frontier.{html,json}`, `report.html`, `metrics.json` (values unchanged; `_meta` shape = known W3 churn) | project-10 pytest exit 0 (project-only coverage 60.43% < 80% threshold — isolated-run artifact, full suite below), ruff/format on project OK, check_headline_numbers OK, gen_static_registry --check OK |
| Q2 apps review | done | `AgentChatArticle.tsx` (single-runs sentence), `apps.ts` (generic provider line) | number audit (all numbers matched committed reports, listed below), web npm test 753 + lint + build, check_docs OK |
| Q3a judge calibration | done (new report file) | new `scripts/build_judge_calibration_report.py`, new `reports/judge_calibration_report.json` | project-01 pytest exit 0 (167 tests), ruff/format OK, mypy OK, check_headline_numbers OK |
| Q5 TabPFN-2 | **STOPPED at step 3** (token/licence acceptance required) | pyproject + uv.lock probed and reverted to pre-Q5 state | PyPI check, licence fetch, import + fit probe; stop per handoff; details in `collaboration/reviews/20261119-tabpfn2-report/00-report.md` |

Final repo-wide gates: `ruff check .` clean, `ruff format --check .` clean,
`mypy libs projects apps` clean (234 files). Full `uv run pytest -q`
re-run from scratch: exit 0, 97.70% coverage (recorded below).

## Numbers changed in Q1 (each checked against its committed source)

| Project | Change | Source |
|---|---|---|
| 03 | "115 flags … (14.8%)" → "17 of 120 flags hit real incidents, 14.2% precision" (caption + Conclusions) | `reports/figures/threshold_sweep.json` takeaway (17/120) |
| 06 | "8/eight references" → "best-known reference on 5 of 56 instances (6 counting `alns_fleet`)" ×4 (training bullet, results table, business summary, `gap_pct` caption), naming the per-instance record | `reports/results.md` (negative gaps on R202, R207, R211, RC105, RC202; 6th RC102 via `alns_fleet`) |
| 09 | short_version live claim → "Live held-out (2026-11-19): 13/13 answers, 6/6 live-grader refusals (h19: calculator-guard error), 19/19 budgets." (≤280 chars; legacy steps/latency dropped from the short copy only — body keeps them); "8 unplanned calls" removed (caption + body); live confirmation added to background, held-out bullet, business summary, results, limits | `collaboration/reviews/20261118-live-confirmation/comparison.md` (13/13, 6/6, 19/19, h19 calculator-guard); 5/6 legacy kept from `reports/kimi-for-coding/metrics.json` |
| 10 | "+69%" → "+70%" ×7 on story surfaces (Q1); ×4 on web surfaces in the review-fix pass below — `cardCopy.ts`, `upliftJudging.ts`, and the two committed auto-diagram specs (`mermaid-to-flow.mjs` regenerates nothing; direct edit was the only path); full `src/` sweep clean | `00-decisions.md` item 6 (2,812/4,026 = 69.9%); +$2,812 revenue-minus-send-cost naming kept |
| 12 | card 3 title → "Gap to the floor holds under resampling."; pointer → "Blocked on the licence decision; TabPFN-2 challenger pending; see README." (73 chars, cap-compliant); review-fix pass: next-card title "External TabPFN-2.5 challenger" → "External TabPFN-2 challenger" (TabPFN-2.5 is not used) | decisions item 7 |
| 13 | "up to 15%" → "13.8% at the c64 throughput cell; p50 medians differ by at most 4%" ×3; "3.3 GB CUDA stack" ×3 and "12.8 GB earlier build" removed from story (Q1); "3.3 GB CUDA"/"12.8 GB" also removed from `docs/projects/13-model-serving.md` + the project README (review-fix pass); "~20%" slope threshold removed | `reports/metrics.json` (max ONNX lead 13.8% at c64; p50 ratios ×0.96–×1.04); sizes kept as the measured record in `DESIGN.md:54`, per the reviewer |
| 02 | spike-capture values 0.845/0.839/0.621/0.601 removed from story body (narrative kept; values stay in DESIGN.md) | decisions item 8; origin-selection sentence already present ("choose on two origins and grade exactly once") |
| 04 | ECE pair 0.0360→0.0227 and "37%" removed from story body, business summary, conclusions, key_concepts (Q1) and from `docs/projects/04-nlp-classification.md` + the project README (review-fix pass); card → "Calibrated probabilities with one temperature." (no number); detail → "0.9460 test-split macro-F1" | decisions item 8 (values kept in DESIGN.md, confirmed at DESIGN.md:115) |
| 11 | "tracing made pandas's group-by look 4x slower" ×2 removed | decisions item 8 (untraceable) |
| 07 | roadmap detail "xGB tested −4.1% better" → "The test leader tested −4.1% better; the holdout has no vote."; title → "Validation winner served; test leader rejected." | `reports/metrics.json` (−4.05% ≈ −4.1%); "served GBM" naming consistent with short copy |

03 VUS-PR wording (Q1.4): no VUS-PR results and no "gamed on NAB" phrase exist
in current copy — nothing to soften; the `next` card mentioning TSB-AD/VUS-PR
is unrendered maintenance state. No change made.

## Q1b detail

The committed figure annotation ($6,698) was stale: `profit_figure`
interpolated the display-decimated curve grid (`_fig_curve`), drifting from
`metrics.json profit_at_budget` (6838.15). Fix: compute the recommended-point
profit from the full-resolution curves on the same nearest-grid semantics as
`evaluate_policies.profit_at`, then decimate for display. Regenerated via
`uv run python -m uplift_experimentation.cli evaluate --params-file params.yaml`
(mandated CLI path; no hand-editing): annotation now reads **$6,838
(t_learner)**; the other 8 figure pairs regenerate byte-identical; metrics
values unchanged (semantic diff vs HEAD: only the known `_meta` stamp ↔
results-block shape churn, flagged for W3).

## Q2 number audit (article/card numbers → committed source)

- 108/108, 16 cases × 3 repetitions, 48 executions → `apps/agent-chat/reports/evals-kimi-for-coding.md`
- 26/33 (k3-256k), 24/33 (k3.1-pro), 33 assertions/pass grader set → `evals-kimi-k3-256k.md`, `evals-kimi-k3.1-pro.md`
- 44.8 s recording, kimi-for-coding → `apps/showcase-web/public/apps/agent-chat-demo.mp4` (44.8 s)
- 10-turn history, 5-note recall / 10 cap → `src/agent_chat/config.py:57`, `src/agent_chat/memory/tools.py:30`
- Six ADRs → `apps/agent-chat/specs/decisions/` (6 files)
- DI: 7 documents / 8 reference pages, entity F1 0.677, topic F1 0.500, summary support 0.818, miss rate 1.00, chat/citation 1.00, resolvability 1.00 / unsupported 0.00, page failure 0.00, p50 38.5 s (31.9 + 6.6) → `apps/document-intelligence/reports/live-metrics.json`
- No DI production-accuracy claim found in article or card (card result "7 PDFs · 8 pages · miss rate 1.00" agrees with the disclaimer framing) — no removal needed.

## Q3a results (new file `reports/judge_calibration_report.json`)

Label set: 194 claims (97 supported / 97 unsupported), labels by construction.

- **Local judge qwen2.5:3b**: FA 0.4433, Wilson 95% [0.3752, 0.5136] — the
  recomputed upper bound matches the committed UCB (0.5136) exactly; kappa
  0.5464 point-only (aggregates committed, no per-claim verdicts).
- **Hosted judge qwen3:4b** (recomputed from committed per-claim
  predictions, 2 runs × 184): pooled FA 0.1875 [0.1509, 0.2305] over all
  claims; strict unsupported-only FA 0.3966 [0.3269, 0.4707]; kappa 0.6052,
  bootstrap 95% [0.5262, 0.6831]; per-run kappa 0.656 / 0.554. The committed
  hosted aggregate (FA 0.4536, kappa 0.5361) does **not** reconcile with its
  own predictions file — flagged in the report (known R7/R8 semantics issue);
  do not quote both together.
- No copy changed (owner reads the result first, per plan).

## Q5 summary

STOP at step 3: `tabpfn 10.2.0` (PyPI current) requires `TABPFN_TOKEN` +
licence acceptance at ux.priorlabs.ai on first `.fit()`. Pin reverted; no
challenger artifacts. Owner decision recorded in OPEN_QUESTIONS (provide
token / drop / raw-HF path). Licence text itself confirmed (v1.1, §10
attribution "Built with PriorLabs-TabPFN" + shipped copy — both still
required if Q5 resumes).

## Review-fix pass (owner-relayed list, applied after the review)

Files changed:
- `apps/showcase-web/src/lib/cardCopy.ts`, `upliftJudging.ts`,
  `diagrams/auto/10-uplift-experimentation-1.ts`, `-4.ts` — "+69%" → "+70%" ×4
  (auto specs are committed artifacts; `mermaid-to-flow.mjs` regenerates
  nothing, so direct edit; full `src/` sweep confirms no "+69%" remains).
- `docs/projects/04-nlp-classification.md`, `projects/04-nlp-classification/README.md`
  — ECE pair + "37%" removed; values kept in `DESIGN.md:115` (confirmed).
- `docs/projects/13-model-serving.md`, `projects/13-model-serving/README.md`
  — "3.3 GB CUDA"/"12.8 GB" removed; kept as the measured record in
  `DESIGN.md:54`, per the reviewer.
- `projects/12-tabular-ml-lifecycle/story.yaml` — next-card title →
  "External TabPFN-2 challenger".
- `projects/10-uplift-experimentation/reports/metrics.json` — restored to
  HEAD after value verification: **0 numeric differences** (all 15 structural
  diffs were `_meta`-only — stamp fields at HEAD vs results blocks in the
  regenerated file, the known W3 churn). `profit_frontier.{html,json}` and
  `report.html` (the Q1b fix) kept.

Gate outputs this pass:
- `lint_story_language.py` — 13 stories, 0 errors, 0 warnings.
- `check_docs.py` — OK.
- `check_short_copy.py --check` — single-sourced, 39 surfaces.
- `gen_story_short.py --check` — current (no regeneration needed; the edited
  web files are not inputs to storyShort).
- `check_headline_numbers.py` — 11 claims, 0 findings.
- Web: `npm test` 753 passed (56 files), `npm run lint` clean,
  `npm run build` succeeded.
- `uv run pytest -q projects/10-uplift-experimentation` — exit 0, 69 tests
  (run `--no-cov`; the project-only coverage threshold fails in isolation, as
  documented earlier — the full-suite coverage gate remains the 97.70% run).

**Correction of earlier claims.** "…+70% everywhere" and "every number
traced" now mean: every surface **found and checked** — the 7 story spots +
the 4 web spots above (sweep-verified), with each changed number traced to
its committed source in the tables. Surfaces found LATER by the reviewer (the
four web spots) were fixed in this pass; any surface neither I nor the
reviewer enumerated is not covered by that claim.

**Surfaces still open** (updated after the xGB/design-note handoff):
1. ~~07 body copy "xGB" naming~~ — **closed 2026-11-19**: "xGB" kept as the
   XGBoost challenger's name with a first-use definition
   (`collaboration/reviews/20261119-xgb-naming-and-design-note/00-report.md`).
2. ~~09 `DESIGN.md` "8 unplanned calls" line~~ — **closed 2026-11-19**:
   historical sentence kept with a correction note (same report).
3. Q5 TabPFN-2 (token/licence acceptance) — OPEN_QUESTIONS pending owner.
4. Q3b / Q3c / all Q4 items — pending owner approval.
5. W3 provenance stamp — separate handoff; note that the metrics.json restore
   above re-applied the stamped `_meta` shape, so Q1b leaves no metrics
   churn for W3 to reconcile on this file.

## Full pytest (final gate, from scratch)

`uv run pytest -q` re-run from scratch: **exit 0, total coverage 97.70%**
(required 80% reached). No failures.

## Remaining for the owner

1. Read Q3a's `judge_calibration_report.json` before any judge-related copy change.
2. Decide Q5 (OPEN_QUESTIONS) — token, drop, or raw-weights path.
3. W3 provenance-stamp handoff (separate, per plan §Q6 note) — Q1b's metrics
   `_meta` shape churn is part of that decision.
4. Commit in parts; production deploy separately (H9/P2/Q1 web changes are
   not live until then).
5. Approve/decline Q3b (hosted, $3 cap), Q3c (model download), and Q4 items
   one at a time.
