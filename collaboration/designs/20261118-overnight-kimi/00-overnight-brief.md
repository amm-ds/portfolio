# Overnight brief for Kimi Code: plan and execute the approved queue

Date: 2026-11-18
Designer: Claude Code
Executor: Kimi Code
Owner: amm-ds (commits and deploys)
Status: approved for overnight execution by the owner.

## Message to Kimi (read first)

You are executing the approved repo queue overnight. Plan the order, run each handoff's steps and gates, and write a morning report. Do not stop for questions that a handoff already answers. Stop only where a handoff's stop condition applies.

Read in this order:
1. `collaboration/reviews/20261117-report-for-kimi/00-master-report.md` (queue, verified facts, corrections, owner decisions recorded 2026-11-18 in section 3).
2. Each handoff listed in section 2 below.

## Hard limits (apply to everything)

- No git mutations: no add, commit, push, branch, stash, or reset. The owner commits.
- No deploys, no changes to `.env`, no changes to permissions or config.
- Paid or hosted model calls: only the held-out run in `collaboration/designs/20261118-live-confirmation-09/03-implementation-handoff.md`, capped at $5 on `kimi-for-coding`. No other hosted calls.
- No full M5 panel rerun. Decision 12 stays open.
- Do not hand-edit generated files. Regenerate them with their scripts.
- Do not edit committed records under `projects/*/data/` in place. Write new outputs to the paths each handoff names.
- Do not change the 360 px per-row height minimum (decision 7).
- Do not add `quality_quant` to `DOCS_FIGURES` (decision 14).
- Do not compute the NAB official score (decision 2).

## Ordered queue

Run in this order. Finish each item's gates before the next. If an item is blocked, skip it, record why in the morning report, and continue.

1. **Metrics guard** — `collaboration/designs/20261117-metrics-guard-fix/03-implementation-handoff.md`. Code and tests only. No redeploy.
2. **Uplift copy** — `collaboration/designs/20261117-10-uplift-review-fixes/03-implementation-handoff.md`. Use 42,613 analysed of 64,000. Rename "profit" to "revenue minus send cost".
3. **NLP cascade interval** — `collaboration/designs/20261117-04-nlp-review-fixes/03-implementation-handoff.md`. Compute from committed predictions only. No API calls.
4. **M5 selection isolation** — `collaboration/designs/20261117-02-m5-review-fixes/03-implementation-handoff.md`. Test and single-origin caveat. Stop if the reconciled number is not committed.
5. **Routing labels and local PyVRP on Solomon** — `collaboration/designs/20261117-06-routing-review-fixes/03-implementation-handoff.md`. Decision 1: run PyVRP locally on Solomon. Expect about 15 minutes of compute. Do not run HGS.
6. **Mobile figure layout** — `collaboration/designs/20261117-mobile-figure-layout/03-implementation-handoff.md`. Legend below the plot under 600 px. Leave the height minimum alone.
7. **Tabular wording and TabPFN-2.5** — `collaboration/designs/20261117-12-tabular-review-fixes/03-implementation-handoff.md`. Decision 8: call MLP and LightGBM a validation tie, and remove the champion label. Decision 11: TabPFN-2.5 for the bike data. Install and run it locally; no hosted calls. If the install or run needs more than an hour of compute, stop and record it.
8. **Serving tail latency** — `collaboration/designs/20261117-13-serving-review-fixes/03-implementation-handoff.md`. p95 and p99 with n. Do not run the standard load tool (decision 6).
9. **Inference labels and cost assumptions** — `collaboration/designs/20261117-08-inference-review-fixes/03-implementation-handoff.md`. Decision 3 is deferred.
10. **Churn cost weights** — `collaboration/designs/20261117-05-churn-review-fixes/03-implementation-handoff.md`. Decision 9: check config first. If the weights are not there, stop this item.
11. **Mobility rounding** — `collaboration/designs/20261117-07-mobility-review-fixes/03-implementation-handoff.md`.
12. **RAG metadata** — `collaboration/designs/20261117-01-rag-review-fixes/03-implementation-handoff.md`. Decision 4 is deferred.
13. **Anomaly headline and intervals** — `collaboration/designs/20261117-03-anomaly-review-fixes/03-implementation-handoff.md`. Decision 2: state that the NAB official score is not reported.
14. **Data-engineering spread and negative test** — `collaboration/designs/20261117-11-dataeng-review-fixes/03-implementation-handoff.md`. Decision 10 is deferred.
15. **Agentic held-out run** — `collaboration/designs/20261118-live-confirmation-09/03-implementation-handoff.md`. Run once under the $5 cap. Then grade offline into the review folder.
16. **Pass-rate intervals** — `collaboration/designs/20261117-09-agentic-review-fixes/03-implementation-handoff.md`. Offline only. Do not call the hosted endpoint.
17. **Hillstrom Qini search** — decision 13. Web search only. Write the findings, with sources, into the SOTA research folder. Do not change code for this item.

Not in the queue: the figure-review handoff (still draft; do not execute), and the metrics fix redeploy (owner's job).

## Gates

After each item, run the gates its handoff lists. Then run, at the end of the night:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run pytest -q
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
```

If a gate fails after two attempts, stop that item, keep the failing output, and move on.

## Stop and escalate

Write `OPEN_QUESTIONS.md` beside the item's handoff and move on when:
- a handoff's stop condition applies;
- spend from the held-out run reaches $4 or more;
- a gate fails twice;
- an instruction needs a decision that is not recorded in the master report.

## Morning report (required)

Write `collaboration/reviews/20261119-overnight-report/00-report.md` with:
- one row per queue item: status (done, blocked, skipped), files changed, commands run, gate results, and any open question;
- the ledger line from the held-out run and the total spend;
- any generated outputs you wrote, with their paths;
- what remains for the owner to review or commit.

Quote numbers exactly. Do not claim a gate passed unless you ran it.
