# Apps and RAG pass — step 1 audit (read-only)

Date: 2026-11-19
Scope: `apps/agent-chat`, `apps/document-intelligence` (both independent uv
workspaces). No code changes in this step. All commands run from each app
directory unless noted.

## 1. Dependency audit

**No dependency-audit tool is configured in the repository.** `pyproject.toml`
and `.github/workflows/ci.yml` contain no pip-audit/uv-audit/or equivalent
invocation (the only "audit" occurrence is npm's `--no-audit` flag). Per the
handoff, no tool was installed and no CVE scan was run; this section records
the gap rather than results. Each app ships its own committed `uv.lock`
(`apps/agent-chat/uv.lock`, `apps/document-intelligence/uv.lock`) — a tool
choice is an owner decision.

## 2. Coverage (measured; becomes the step-5 floor)

Neither app depends on pytest-cov, so coverage was measured with an
ephemeral tool environment (`uv run --with pytest-cov pytest ...`); no
dependency was added to either app.

| App | Suite result | Statements | Missed | Coverage | Floor (round down, 1 dp) |
|---|---|---|---|---|---|
| agent-chat | exit 0 | 1744 | 177 | 89.85% | **89.8** |
| document-intelligence | exit 0 | 1947 | 300 | 84.59% | **84.5** |

## 3. Lint and types on `src/`

| App | `ruff check src` | `mypy src` |
|---|---|---|
| agent-chat | All checks passed | Success, 43 files |
| document-intelligence | All checks passed | Success, 39 files |

Zero findings in both apps — there are no real bugs, style findings, or
false positives to classify. Step 2 therefore has nothing to fix from lint.

## 4. Error response shapes

Both apps use the same contract, implemented independently:

```json
{"error": {"code": "...", "message": "...", "request_id": "..."}}
```

- **agent-chat** (`src/agent_chat/api/app.py`): handlers for `HTTPException`
  (`http_<status>`), `RequestValidationError` (`validation_error`, 422), and
  a catch-all `Exception` → 500 `internal_error` whose message is only
  `type(exc).__name__`; the traceback is logged server-side
  (`logger.exception`), never returned. `request_id` comes from the request
  state (RequestIdMiddleware).
- **document-intelligence** (`src/document_intelligence/api/app.py`):
  `DocumentNotFoundError`/`PageNotFoundError`/`BlobNotFoundError` → 404,
  `DocumentBusyError` → 409, `ValueError` → 400 `invalid_request`,
  `HTTPException` (`http_<status>`), validation → 422, `/ready` → 503 with
  the health body when a store is down; catch-all returns the same envelope.

No handler emits a traceback or a server path; messages are `str(exc)` of
controlled domain exceptions. FastAPI runs with `debug=False` (neither app
enables it). Residual risk: any exception whose message embeds an internal
path would pass through `str(exc)` — none was found in the enumerated paths.
Step 4 adds tests pinning this contract.

## 5. Health, readiness, and compose healthchecks

| App | `/health` | `/ready` | Compose healthcheck |
|---|---|---|---|
| agent-chat | yes (`routes_admin.py:36`, liveness) | yes (`:47`, probes stores) | **api service has none** — only `depends_on: db (service_healthy)`; the db service healthcheck is `pg_isready` |
| document-intelligence | yes (liveness) | yes (probes repository + queue, 503 when down) | api targets `/ready` ✓; worker healthcheck imports the module ✓ |

The agent-chat api service has no healthcheck target to verify. Fixing it
would edit a deployment file, which this pass excludes (except rate-limit
wiring) — reported as an observation for the owner, not changed.

## 6. Duplicate contracts (proposal item 8 — note only, no refactor)

The two apps independently implement the same error envelope
(`_error_body` / `error_body`), a request-id middleware, and header-based
identity checks (`security.py` vs `identity.py`). Per the proposal, no
cross-app refactor in this pass.

## Stop-condition check

None applies: no dependency upgrade needed (nothing installed), no committed
record touched, no hosted call made. Continue to step 2 (no lint real bugs
to fix; the step will be a no-op recorded as such).
