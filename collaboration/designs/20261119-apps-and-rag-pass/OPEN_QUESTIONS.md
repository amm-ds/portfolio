# OPEN QUESTIONS — apps and RAG pass

## Step 5 coverage floor: blocked on a new dependency (held, not applied)

Step 5 asks for a coverage floor in each app's pytest configuration. Neither
app has any coverage tooling: `pytest-cov`/`coverage` appear nowhere in
`apps/agent-chat/uv.lock` or `apps/document-intelligence/uv.lock`
(verified by grep, 0 hits), and step 1 measured coverage with an ephemeral
`uv run --with pytest-cov` so nothing was added.

Enforcing a floor requires a pytest plugin (`pytest-cov`), which is a new
dependency — prohibited by the standing rules ("No new dependencies...
If a finding can only be fixed by an upgrade, stop and report it"). Adding
the config without the plugin would break every test run (unrecognized
`--cov` arguments, verified empirically).

Held, with the step-1 measurements ready to wire once the owner decides:

| App | Measured coverage | Floor to set (round down, 1 dp) |
|---|---|---|
| agent-chat | 89.85% (1744 stmts, 177 missed) | **89.8** |
| document-intelligence | 84.59% (1947 stmts, 300 missed) | **84.5** |

Owner decision needed: approve `pytest-cov` as a dev dependency for both
apps (then the floor is a one-line `addopts` change per app), or leave the
apps without an enforced floor.
