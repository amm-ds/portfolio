# Implementation handoff: 13 serving tail latency and parity-gate test

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided)
Source review: `collaboration/reviews/20261117-experiment-review/13-model-serving.md`

## Objective

Report p95 and p99 with sample sizes in the headline and figure, add a test that the parity gate fails above tolerance, and reference one standard load tool on the top cell.

## Scope

### In scope
- `projects/13-model-serving/src/model_serving/` (tail-percentile reporting; parity gate test target)
- `projects/13-model-serving/tests/` (parity gate test)
- `projects/13-model-serving/README.md` and `story.yaml` (headline table, short copy)
- `reports/metrics.json`, `reports/figures/latency_concurrency_lines*` (p99 band, n per cell)
- Regenerated: `apps/showcase-web/src/lib/storyShort.ts` if `short_version` changes

### Out of scope
- Changing the serving code paths or the ONNX export
- New backends
- Image-size work

## Ordered steps

1. **Tail metrics.** Add p95 and p99 with the per-cell request count to `metrics.json` from the existing nearest-rank percentile code. Do not change the percentile method.
2. **Headline table.** Add p95, p99, and n beside the p50 headline. Keep the one-machine sentence in the same sentence as the req/s figure.
3. **Figure.** Add a p99 band or markers to `latency_concurrency_lines`, labelled with n.
4. **Parity-gate test.** Add a test that the gate raises or reports failure when max-abs exceeds 1e-4, using a perturbed fixture.
5. **Standard load tool.** Owner decision: running `locust` or `wrk` on the top cell is a new measurement. Do not run it until the owner approves; if approved, report it beside the harness numbers with its version and command.

## Commands and gates

```bash
uv run pytest -q projects/13-model-serving/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] p95, p99, and n per cell in `metrics.json` and the headline table.
- [ ] Figure shows p99 with n.
- [ ] Parity-gate test fails on a perturbed fixture above 1e-4 and passes on the committed model.
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Pause before running the standard load tool; it needs owner approval.
