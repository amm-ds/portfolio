# Review response: execution plan Q1, Q1b, Q2, Q3a, Q5

Date: 2026-11-18
Reviewer: Claude Code
Implementation: working tree on `main`, uncommitted (Kimi report at `collaboration/reviews/20261119-execution-report/00-report.md`)
Status: changes requested

## Verdict

Most of the approved work is in place. Verified by reading the files: the 11 roadmap titles from third-pass §B, the 03 "17 of 120 / 14.2%" correction, the 06 "5 of 56 (6 with alns_fleet)" count (re-derived from `reports/results.md`), the 09 live-claim rewrite, the 10 annotation at $6,838 (`profit_frontier.html`), the 12 card fixes, the 13 "13.8% / ≤4%" rewrite, the Q3a local-judge figures (FA 0.4433, UCB 0.5136, kappa 0.5464 reconcile with the committed record), and the Q5 stop (tabpfn absent from `pyproject.toml`, OPEN_QUESTIONS written).

The report overstates completeness. "+70% everywhere" and "every number traced" are not true: stale copy survives on public surfaces, one roadmap `next` title contradicts the licence decision, and the Q1b regeneration rewrote a committed record with large churn. These need fixing before the owner commits.

## Required changes

| Severity | Finding | Evidence | Required resolution |
|---|---|---|---|
| major | "+69%" survives on card and diagram copy. Plan: "+70%" everywhere. | `apps/showcase-web/src/lib/cardCopy.ts:63`; `apps/showcase-web/src/diagrams/upliftJudging.ts:34`; `apps/showcase-web/src/diagrams/auto/10-uplift-experimentation-1.ts:25`; `…-4.ts:19` | Change each to +70%. Regenerate or re-check `storyShort.ts` if it derives from the same copy. Re-run web gates. |
| major | ECE pair and "37%" remain in project copy. Decision: remove from roadmap and story body, keep in DESIGN.md. | `docs/projects/04-nlp-classification.md:94-95`; `projects/04-nlp-classification/README.md:256` | Remove from the docs page and README (README is public), keep in DESIGN.md. Check whether `docs/projects/*.md` is generated; no generator script was found, so edit the source. |
| major | Hardware sizes remain: "3.3 GB CUDA", "12.8 GB". Decision: remove. | `docs/projects/13-model-serving.md:78-79`; `projects/13-model-serving/README.md:94` ("~3.3 GB of unused CUDA"); `projects/13-model-serving/DESIGN.md:54` (design doc, may stay) | Remove from docs page and README. DESIGN.md may keep them as a measured record, but say so in the report. |
| major | Unrendered 12 `next` card title still reads "External TabPFN-2.5 challenger". Decision: TabPFN-2.5 is not used. | `projects/12-tabular-ml-lifecycle/story.yaml:429` | Retitle to a TabPFN-2 wording. The detail already says "TabPFN-2 challenger pending". |
| major | Q1b regeneration churned a committed record. `metrics.json` shows 717 insertions and 430 deletions, while the report says "values unchanged". The churn is the W3 `_meta` shape issue. | `git diff --stat -- projects/10-uplift-experimentation/reports`: `metrics.json` +717/−430, `report.html` 16, `profit_frontier.json` 2 | Owner decision. Recommended: restore `metrics.json` to HEAD (the figure fix does not need it changed) after confirming `profit_at_budget` values are identical, and keep `profit_frontier.*` and `report.html`. Report the decision. |
| minor | 07 keeps "xGB" in copy (story body, the test-leader and challenger text, `docs/projects/07-open-data-mobility.md`). Plan item 2 says "served GBM" everywhere. Only the roadmap changed. | `projects/07-open-data-mobility/story.yaml:27,188-205,328,361-372`; `docs/projects/07-open-data-mobility.md:38,52,60` | Rename the model to "served GBM" in copy, or record the copy rename as deferred. Note that `xGB versus naive` is also a predeclared comparison label. |
| minor | "8 unplanned calls" survives in the design doc. Decision: remove the sentence. | `projects/09-agentic-workflows/DESIGN.md:181` | Remove, or record that DESIGN.md is out of Q1 scope. |
| minor | Report says "Every number traced" and "+70% everywhere". Both claims were false for the surfaces above. | `collaboration/reviews/20261119-execution-report/00-report.md` | Correct the report to list the surfaces actually changed and the ones still open. |

## Accepted (verified)

- Roadmap: all 11 §B titles present (01 ×2, 06, 07, 08, 09, 10, 11, 12; 04 uses the detail rename "0.9460 test-split macro-F1"). Shipped cards 3–5 per project, every detail ≤ 82 characters.
- 06 count: re-derived from `results.md`. ALNS gap < 0 on 5 instances (R202, R207, R211, RC105, RC202). RC102 is negative only through `alns_fleet`. The "5 of 56 (6 counting alns_fleet)" wording is correct.
- 03: no VUS-PR results appear in copy, so "run count and seed spread" has no target. The only mention is an unrendered `next` card. Accepted.
- 10 annotation: `profit_frontier.html` reads 6,838; the writer fix in `projects/10-uplift-experimentation/src/uplift_experimentation/evaluate.py` computes from the full-resolution grid with `argmin`, matching `profit_at` (line 86). Owner should read the diff once (it is a code change beyond "regenerate").
- Q3a: `judge_calibration_report.json` is a new file. Local judge reconciles. The hosted judge's committed aggregate (FA 0.4536) does not reconcile with its own predictions, and the report says so. Do not quote both together.
- Q5: stopped at the stop condition. The pin is out of `pyproject.toml` (tabpfn count 0). `OPEN_QUESTIONS.md` is correct.
- Hosted spend $0.00 (no hosted calls found in the report's commands). Not independently verified against logs.

## Suggestions

| Suggestion | Reason | Owner decision needed |
|---|---|---|
| Restore `metrics.json` to HEAD and keep only figure and `report.html` changes | Removes 1,100 lines of churn from a committed record | yes |
| Add a check that scans `apps/showcase-web/src`, `docs/projects` and each `README.md` for the retired strings (`+69%`, `0.0360`, `3.3 GB`, `12.8 GB`, `xGB`, `TabPFN-2.5`) | The sweep missed these surfaces; a gate would catch them | optional |
| Decide 07 naming (served GBM or xGB) for the comparison labels | "xGB versus naive" is a predeclared label; renaming it changes the stored record | yes |

## Verification checked

- [x] Scope matches the approved plan (Q1, Q1b, Q2, Q3a, Q5; Q3b, Q3c, Q4 not run)
- [ ] Tests cover the behavior change (Q1b writer change: project 10 pytest reported, not re-run here)
- [x] Generated artifacts are source-derived (figure via CLI; calibration via script)
- [ ] Public copy remains evidence-backed (stale surfaces above)
- [ ] Touched gates are green (Kimi reports them; I did not re-run them)

## Closure

- Required findings resolved: none yet (five major, three minor open).
- Remaining risks: stale public copy on the card, docs, and README surfaces; the `metrics.json` churn; the Q1b writer change needs owner review; the report's completeness claims.
- Recommended next step: send Kimi a short fix list for the five major items (cardCopy and diagram +70%, docs/README ECE and hardware sizes, the 12 `next` title, metrics.json restore) and re-run the web and docs gates. Then review the diff again before the owner commits.
