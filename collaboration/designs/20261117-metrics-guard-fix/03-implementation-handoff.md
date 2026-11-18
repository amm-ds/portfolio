# Implementation handoff: showcase metrics guard rejects the 02 full-panel payload

Date: 2026-11-17
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-17)
Source design: none; this is a root-cause fix small enough for a direct handoff. Split from `collaboration/designs/20261117-figure-review/` because it is a separate defect.

## Root cause (confirmed by reading source and the live payload)

`apps/showcase-web/src/api.ts:96` `getMetrics` validates the response with:

```ts
(value): value is Metrics => isRecord(value) && Object.values(value).every(isRecord)
```

This requires every top-level value to be an object. Project 02 is served from `reports_m5_full/metrics.json` (`_metrics_file` in `apps/showcase-api/src/showcase_api/main.py:357`). That file has top-level values that are not objects:

- `candidates`: list
- `pooled_strategy`: string
- `protocol`: string

The guard rejects the payload, `getMetrics` throws, `ProjectDetail.tsx:~127` sets `metricsStatus` to `"error"`, and the page shows "Metrics could not be loaded. Retry" on every load. Retry cannot succeed because the payload is the same each time.

Live check on 2026-11-17: `https://alejandromerida.dev/projects/02-demand-forecasting/metrics` returns 200 with exactly those keys. Local `projects/02-demand-forecasting/reports_m5_full/metrics.json` has the same keys.

The same guard also breaks projects 08 and 11 on prod, which show "Metrics could not be loaded" too. Their payloads have non-object top-level values: 08 has `cells` (list), `full` (boolean), `ollama_version` and `platform` (strings); 11 has `protocol` (string). The web pass on 2026-11-17 checked all 13 project endpoints: 02, 08 and 11 fail, and the other ten return only object values.

Caveat: the prod deploy is git_sha `b2b5b22`, and local HEAD is `a879fb5`. The defect is in the local source; confirm the prod bundle has the same guard before closing.

## Scope

### In scope

- `apps/showcase-web/src/api.ts` (`getMetrics` guard only)
- A test in `apps/showcase-web/src/__tests__/` that feeds a payload with a list and a string top-level value and expects `getMetrics` to return it
- Any consumer code that breaks once non-object top-level values reach it (read first; see step 2)

### Out of scope

- Metrics payload content or schema in Python
- Any figure generator
- Changes to `ProjectDetail.tsx` retry logic
- Git mutations

## Ordered steps

1. Reproduce: add the failing test first, with a payload shaped like `reports_m5_full/metrics.json` (top-level list and string values). Confirm it fails on the current guard.
2. Read every consumer of `Metrics` (`MetricsTable`, `CaseStudy`, `computeCallouts` in `lib/delta.ts`, and anything that iterates `Object.values(metrics)`). List which ones assume object values. Fix only what breaks with the new guard.
3. Change the guard to accept any non-array object at the top level, and type the 02 keys honestly if the `Metrics` type requires it. Prefer a narrower guard over a looser type. Do not add a fallback that silently hides a bad payload.
4. Run the tests and build. Re-run the page check at `http://localhost:4321/projects/02-demand-forecasting` against a local API started from source, and confirm the error box is gone.
5. Report the exact lines changed and the local result. Do not claim the prod site is fixed; that needs a redeploy by the owner.

## Commands

```bash
cd apps/showcase-web && npm ci && npm test && npm run lint && npm run build
uv run pytest -q apps/showcase-api
```

For the local page check: `uv run uvicorn showcase_api.main:app --port 8000` in `apps/showcase-api`, then `npm run dev` in `apps/showcase-web` (port 4321, proxies `/projects` to the API).

## Acceptance criteria

- [ ] The new test fails before the change and passes after.
- [ ] `/projects/02-demand-forecasting` loads its metrics locally with no "could not be loaded" box.
- [ ] Other projects' metrics still load (spot-check 01 and 08 locally).
- [ ] Gates pass, or failures are reported with output.

## Stop conditions

Write `OPEN_QUESTIONS.md` beside this handoff and pause if a consumer needs a schema decision (for example, whether list values should render in `MetricsTable`).
