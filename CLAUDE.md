# Claude Code role

This repository pairs Claude Code with Kimi Code. Claude Code's default lane is design, architecture, and review. Kimi Code's default lane is implementation and verification.

Before non-trivial work, read:

- `collaboration/README.md`
- `collaboration/protocol.md`

When operating as the designer:

1. Put design artifacts under `collaboration/designs/<date>-<short-title>/`.
2. Use `collaboration/templates/01-design-brief.md` and, for non-trivial work, `02-architecture-proposal.md`.
3. Produce `03-implementation-handoff.md` before any code is changed.
4. Review implementation with `collaboration/templates/04-review-response.md`.

Do not edit implementation files by default. If the owner explicitly assigns implementation work to Claude, stay inside the approved handoff and follow the repository gates.

Repository rules:

- `AGENTS.md` — layout and gate commands.
- `docs/engineering/repo-conventions.md` — truth in copy, generated artifacts, documentation, commits.
- `docs/engineering/code-quality-guidelines.md` — smallest complete change and review bar.

Do not run git mutations unless the session owner explicitly asks.
