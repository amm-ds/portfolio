# Implementation handoff: 06 routing comparator labels, unhinted arm, and instance intervals

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided; the HGS comparator and the vehicle-delta investigation are owner decisions, see below)
Source review: `collaboration/reviews/20261117-experiment-review/06-routing-optimization.md`

## Objective

Stop the CP-SAT arm from reading as independent evidence, report the unhinted arm beside it, add instance-level intervals to the mean gap, and fix the family figure per the figure-review handoff.

## Scope

### In scope
- `projects/06-routing-optimization/src/routing_optimization/evaluate.py` (labels, interval computation, unhinted table)
- `projects/06-routing-optimization/src/routing_optimization/figures.py` (labels only; the family fix is in the figure-review handoff)
- `projects/06-routing-optimization/tests/` (new tests)
- `projects/06-routing-optimization/README.md`, `DESIGN.md` (results text), `story.yaml` (`short_version` and the solver-ladder wording)
- Regenerated: `reports/metrics.json`, `reports/results.md`, `reports/report.html`, and their figures
- `apps/showcase-web/src/lib/storyShort.ts` (regenerated)

### Out of scope
- Adding HGS or any new solver (owner decision, see below)
- Changing ALNS parameters or the hierarchy objective
- The family_gap axis fix (owned by the figure-review handoff)

## Ordered steps

1. **Label the hinted arm.** Everywhere `ortools_cp` appears in copy, figures, and tables, add "ALNS-hinted; not independent of ALNS". Do not rename the key unless a grep-verified rename is trivial.
2. **Report the unhinted arm.** Promote `unhinted_cp_sat` from `metrics.json` into the README solver ladder beside the hinted arm, with its runtime. Do not change how it is computed.
3. **Instance-level interval.** Add a bootstrap over the 56 instances (2,000 resamples, fixed seed) for mean distance gap and for the ALNS vs unhinted difference. Commit the interval to `metrics.json`.
4. **Lead with wins.** Put the `by_distance` win counts (ALNS 52 of 56) in the README summary, beside the mean.
5. **Tests.** Add a test that the bootstrap is deterministic for a fixed seed, and a test that the hinted label is set whenever the hint is used.
6. Regenerate the outputs with the project CLI (`uv run python -m routing_optimization.cli all` or the narrowest regeneration target). Do not hand edit generated files.

## Owner decisions required before Kimi proceeds

- **HGS comparator.** Adding a state-of-the-art heuristic (for example hybrid genetic search) is new scope and a new design. It is not part of this handoff. Owner decides whether to start a separate design.
- **Vehicle delta (+3.7).** Investigating the ALNS objective weighting is a research question. Kimi should not change the objective. Owner decides whether to open a design for it.

## Commands and gates

```bash
uv run pytest -q projects/06-routing-optimization/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/gen_route_manifest.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Every mention of the CP-SAT hinted arm carries the non-independence label.
- [ ] The unhinted arm appears beside it with its runtime.
- [ ] Instance-level interval committed in `metrics.json`, seed fixed.
- [ ] Win counts lead the summary.
- [ ] Tests pass; the determinism test fails if the seed is removed.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause if the unhinted arm is incomplete for any instance, and report the count rather than filling gaps.
