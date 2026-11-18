# Implementation handoff: 01 RAG reporting fixes

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17; items marked "Owner decision required" stay blocked until decided; the BM25 reference arm is an owner decision, see below)
Source review: `collaboration/reviews/20261117-experiment-review/01-rag-agent.md`

## Objective

Record the judge model and RAGAS version on the card and in metrics, present the 30-question stress result as counts with denominators, and label the figure axes with n.

## Scope

### In scope
- `projects/01-rag-agent/src/rag_agent/` (metadata fields only: judge model, RAGAS version)
- `projects/01-rag-agent/reports/metrics.json` (new metadata fields)
- `projects/01-rag-agent/README.md` and `story.yaml` (stress-result wording, judge and RAGAS line)
- Figures `failure_taxonomy`, `retrieval_funnel` (axis n labels only)
- `apps/showcase-web/src/lib/storyShort.ts` if the short copy changes

### Out of scope
- Adding the BM25 reference arm (new retrieval arm; owner decision)
- Re-running any judge or generation call (paid hosted endpoint; owner approval required)
- Changing the held-out set or the tuning set

## Ordered steps

1. **Metadata.** Read the RAGAS version from `uv.lock` and the judge model from the committed run config. Write both into `metrics.json` under `_meta`. If either is not in the repo, stop and report.
2. **Stress wording.** Present "11 → 5 unsupported" as "5 of 30 unsupported (was 11 of 30)" in the README and copy. Add "CI width exceeds the change; not a demonstrated gain".
3. **Axis n.** Add n to the rate axis labels on `failure_taxonomy` and `retrieval_funnel`.
4. Regenerate the two figures with the project CLI. Do not call any model.

## Owner decision required

- **BM25 + reranker reference arm.** A new retrieval baseline is a new experiment with its own design and possibly paid reranker calls. Owner decides whether to open a design.

## Commands and gates

```bash
uv run pytest -q projects/01-rag-agent/tests
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
uv run python scripts/gen_story_short.py && uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
```

## Acceptance criteria

- [ ] Judge model and RAGAS version present in `metrics.json` and on the card, each traced to a committed file.
- [ ] Stress result appears as counts with denominators, and the CI note is present.
- [ ] Figure axes show n.
- [ ] No model call made; gates pass, or failures are reported with output.

## Stop conditions

Pause if the judge model or RAGAS version is not committed.
