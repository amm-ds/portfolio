# Improvement pass: apps and RAG (project 01)

Date: 2026-11-19
Author: Claude Code (designer)
Status: proposal for owner decision. Nothing here is approved yet.
Inputs: survey of `apps/agent-chat`, `apps/document-intelligence`, `projects/01-rag-agent` (read-only, 2026-11-19); `collaboration/reviews/20261119-next-round-2-report/00-report.md`; `collaboration/designs/20261119-next-round-2/00-proposal.md`

## What the survey found

- **Auth exists.** agent-chat requires `X-API-Key` on chat endpoints (`apps/agent-chat/src/agent_chat/api/security.py`). document-intelligence authenticates through `api/identity.py`.
- **No rate limiting** found in either app's `src/`. Chat and upload endpoints are unthrottled.
- **No tracked local artifacts.** No `.db`, memory directories, `__pycache__` or `node_modules` are committed.
- **Deploy files exist** for both apps (`infra/Dockerfile`, `infra/docker-compose.yml`), and the production compose files are in `deploy/`.
- **No TODO/FIXME** markers in the apps or RAG project.
- **Test counts are real.** Roughly 130 tests in agent-chat, 60 in document-intelligence, 115 in RAG (in test files, not checked by running them).
- **Two `print` calls** in agent-chat's `evals/runner.py` and `rag/ingest.py` write JSON to stdout. These are CLI outputs, so they are fine.
- **RAG verify-on copy** now states the measured judge miss rate (0.4433 local, 0.3966 hosted, strict). The judges still miss about 40% of unsupported claims, so the check is measured but not reliable.

## Gaps this pass should close

Grouped by what they protect:

### A. Production readiness (apps)

1. **Rate limiting on expensive endpoints.** Chat and upload endpoints call paid models and need a per-key limit. Add a limiter (in-process first; the design should say so) with tests that show a 429.
2. **Health and readiness split.** Confirm `/health` and `/ready` exist and that compose healthchecks use them, in both apps. Add a test per app.
3. **Secrets and config.** Check that no default key or secret reaches a production image. The test value `offline-test-key` is fine in tests only; confirm it cannot be the production default.
4. **Dependency and image audit.** Run the existing dependency audit on both `uv.lock` files and report the findings. No upgrades without a separate decision.
5. **Error contracts.** Check that API errors return a consistent shape and that no stack traces reach clients. Add tests for the error shape.

### B. Code quality (apps)

6. **Coverage floor.** Run each app's tests with coverage, record the number, and set a floor at the measured value (no higher).
7. **Lint and types.** Run `ruff` and `mypy` on each app's `src/`. Fix findings that are real bugs. Do not restyle the code.
8. **Duplicate contracts.** Where the two apps repeat the same security or identity code, note it in the report. Do not refactor across apps in this pass.

### C. Results and quality (RAG project 01)

9. **Retrieval baseline (R4).** Compare the current retriever with BM25 on the same sealed set. Report recall@5 with intervals. Offline, no hosted calls, if the sealed set is already committed.
10. **Judge re-check (R1).** Re-measure each committed judge on the 194-claim label set. This is already done (Q3a). Do not re-run it; instead, add per-judge intervals to the copy only if the owner approves a copy change.
11. **Error budget card (R5).** Report cost per query, latency median and p95, and the unsupported rate with its interval, side by side. Compute from committed metrics only.

## Items that need hosted spend or a decision (held)

- **R2, warrant-strength check (Q3b).** Hosted judge run, $3 cap on `kimi-for-coding`. Not approved. This is the only way to measure whether a relevant citation backs an overstated claim.
- **R3, grow the sealed set to 100+.** Needs a new sealed set and a run. Costs money. Held.
- **App live evals beyond the committed runs.** Held: any new live run needs a cap.

## Proposed order

1. Read-only audit (items 4, 5, 6, 7) first, with a report. No code changes yet.
2. Fixes for real bugs found in step 1, plus tests for items 1, 2 and 5.
3. Offline RAG items 9 and 11.
4. Report. The owner decides on R2 and R3 after reading it.

## Stop conditions

- A fix would change a committed record or a headline number: stop and write `OPEN_QUESTIONS.md`.
- A hosted call is needed that is not listed above: stop.
- A dependency upgrade is needed to fix a finding: stop and report.

## Owner decisions needed

1. Approve steps 1–4 (offline, $0).
2. Rate-limit design: in-process limiter now, or a shared store (Redis) as a later item?
3. R2 warrant check ($3 hosted, `kimi-for-coding`): approve or hold?
4. R3 new sealed set: approve or hold?
