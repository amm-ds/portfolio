# Claude ↔ Kimi collaboration

Use this workspace when design and execution should be separated across two coding agents. Claude Code frames the problem and owns architecture and review. Kimi Code executes the approved handoff and proves the change.

## Roles

| Agent | Owns | Does not own by default |
|---|---|---|
| Claude Code | design briefs, architecture proposals, tradeoff analysis, review responses | implementation edits, test execution, artifact regeneration |
| Kimi Code | implementation, tests, focused refactors, artifact regeneration, verification reports | redesigning approved contracts or broadening scope |

The session owner approves the design before execution and commits the finished work.

## Start side by side

```bash
make collab
```

The launcher uses tmux when available: Claude Code on the left, Kimi Code on the right, both launched from the repository root so each agent reads its own role contract.

## Artifact flow

1. Claude creates a dated design directory from `templates/01-design-brief.md` and, for non-trivial work, `templates/02-architecture-proposal.md` under `designs/`.
2. The session owner approves the design. Status moves from `draft` to `approved`.
3. Claude completes `templates/03-implementation-handoff.md` with exact scope, files, commands, and acceptance criteria.
4. Kimi executes the handoff, edits only the approved scope, and records evidence in the implementation summary.
5. Claude reviews with `templates/04-review-response.md` under `reviews/`.
6. Kimi resolves required findings and reruns the touched gates.

## Working agreement

- Claude does not edit implementation files unless the owner explicitly changes the role for a task.
- Kimi does not silently redesign an approved contract. If the design is ambiguous or wrong, stop and add `OPEN_QUESTIONS.md` beside the handoff.
- Both agents follow `AGENTS.md`, `docs/engineering/repo-conventions.md`, and `docs/engineering/code-quality-guidelines.md`.
- Public copy and metrics claims must trace to committed artifacts.
- Generated registries and reports are rebuilt with their scripts, never edited by hand.
- Agents do not run git mutations by default. The session owner commits.
- Each finished turn reports files changed, commands run, gate results, and unresolved risks.

## Directory map

- `protocol.md` — detailed operating loop and escalation rules.
- `templates/` — canonical design, handoff, and review formats.
- `designs/` — approved and in-flight design artifacts.
- `reviews/` — Claude review responses and disposition.
