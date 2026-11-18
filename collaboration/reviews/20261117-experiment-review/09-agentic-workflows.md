# 09 · Agentic workflows: technical review

## Verdict
Deterministic grading and an explicit, honest "live confirmation pending" flag. The architecture is auditable. The results are legacy measurements, so no new contract (deadlines, refusals, typed outcomes) has live evidence yet.

## Architecture
- Plan → act → critique → review workflow with typed terminal outcomes, no-evidence handling, and enforced deadlines. Good separation of graded outcomes from free text.
- Grading runs offline from recorded run records. Reproducible and cheap to re-grade.
- Tool discipline pass tightened prompts and added a critique step that audits tools against the plan. Documented in the README.

## Results vs benchmarks and SOTA
- The benchmark is a small in-house suite (15 tuning tasks, 13 unseen, 6 refusals). There is no public agent benchmark on this task set. Compare, if at all, to a published agent benchmark category (for example a tool-use or function-calling benchmark, **verify** the name and version before citing).
- The copy correctly does not claim SOTA.

## Metrics and statistics
- 15/15 fixed, 13/13 unseen, 5/6 refusals, 18/19 steps, 12/19 latency: these are counts with denominators. Keep them that way.
- Latency pass rate 12/19 is the weakest number and the copy states it. Keep it visible in the headline.
- Single run per task. With 15 tasks, a pass rate has wide intervals; state that.
- The new contracts (6/6 refusals, deadline behaviour) have no live run. The headline must not imply they are verified.

## Code and tests
- 11 test files, deterministic tests for the new contracts. Good. Those tests check logic, not live model behaviour, which the copy already separates.

## Visuals
- `node_waterfall` and `cost_latency_bars` support the latency story. Label which run each bar comes from (legacy vs live).

## Copy and articles
- short_version states "Live confirmation pending". Keep it.
- The results table lists per-task latency in seconds; consider p50 across repeats if repeats exist.

## Kimi refinement tasks
1. (major) Run the live confirmation for the new contracts (deadlines, refusals, answer preservation) and publish it beside the legacy numbers. This needs owner approval: it spends model calls.
2. (major) Add confidence intervals or at least a per-task repeat count to the pass rates.
3. (minor) Label legacy versus live runs on every figure.
