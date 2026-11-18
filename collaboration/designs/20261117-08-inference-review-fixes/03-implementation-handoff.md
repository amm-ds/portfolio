# Implementation handoff: 08 guardrail framing, cost assumptions, and tests

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided; the harder quality task is an owner decision, see below)
Source review: `collaboration/reviews/20261117-experiment-review/08-inference-serving.md`

## Objective

Stop the saturated quality check from reading as a quality result, put the electricity-cost assumptions on the card beside the figure, and add unit tests for the percentile and cost code.

## Scope

### In scope
- `projects/08-inference-serving/src/inference_serving/figures.py` (`fig_quality_quant` labels and table text only; the contrast fix is in the figure-review handoff)
- `projects/08-inference-serving/src/inference_serving/bench.py` (percentile and cost helpers, tests only; no logic change)
- `projects/08-inference-serving/tests/` (new unit tests)
- `projects/08-inference-serving/README.md` and `story.yaml` (cost assumptions and guardrail wording)
- `reports/metrics.json` (cost assumption fields, if not already present)

### Out of scope
- Adding a harder quality task (owner decision, see below)
- Re-running any benchmark cell (hardware time; owner approval required)
- Changing the engine or model set

## Ordered steps

1. **Guardrail framing.** In `fig_quality_quant` and the README, label the check as "saturated smoke check; ties at 1.00; does not establish quality". Keep the existing takeaway text but make the label explicit in the table title.
2. **Remove from headline.** Move the quality table out of the headline visual set in the README (keep it in the detail section). Do not delete the figure file.
3. **Cost assumptions.** Beside the $0.12 per 1M output tokens figure, state the power draw, measured tok/s used, and electricity rate, using values already in the repo. If any value is not committed, stop and report it; do not invent one.
4. **Tests.** Add unit tests for nearest-rank percentiles (including the boundary case) and for the cost calculator (a worked example with known inputs).
5. Regenerate only the figure outputs whose labels changed, using the project CLI.

## Owner decision required

- **Harder quality task.** A task that discriminates between quantization arms (for example a multi-step extraction with a held-out answer key) is new benchmark design and new model runs. It is not part of this handoff. Owner decides whether to open a design.

## Commands and gates

```bash
uv run pytest -q projects/08-inference-serving/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] The quality table is labelled as a saturated smoke check in its title and README section.
- [ ] Cost assumptions appear beside the $0.12 figure, each traced to a committed value.
- [ ] Percentile and cost tests pass with a worked example.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause if any cost assumption is not in the repo, and report it instead of supplying a value.
