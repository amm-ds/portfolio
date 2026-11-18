# Collaboration protocol

This is the operating loop for side-by-side Claude Code and Kimi Code sessions. It is intentionally file-based so either agent can resume from the repository alone.

## 1. Intake

Claude starts a design directory:

```text
collaboration/designs/YYYYMMDD-short-title/
├── 01-design-brief.md
├── 02-architecture-proposal.md   # non-trivial changes
├── 03-implementation-handoff.md
└── OPEN_QUESTIONS.md             # only when execution is blocked
```

Use one directory per logical change. Do not mix unrelated work in the same handoff.

## 2. Design

Claude writes the smallest design that fully solves the problem.

Required qualities:

- The problem and success criteria are explicit.
- Every material claim links to a committed artifact, code path, or prior decision.
- Alternatives are compared by operational cost, risk, and reversibility.
- Contracts, data ownership, failure behavior, observability, and rollback are named.
- The default recommendation is the smallest complete change, not the most general architecture.

Claude may inspect code and run read-only checks while designing. Claude does not edit implementation files in this phase.

## 3. Approval

The session owner reviews the design and either:

- approves it by changing status to `approved`, or
- sends it back with requested revisions.

Kimi does not start implementation from a draft or superseded design.

## 4. Handoff

The handoff must be executable without oral context. It includes:

- affected files and directories;
- exact ordered implementation steps;
- tests and gates to add or rerun;
- generated artifacts and their regeneration commands;
- data, provider, or deployment constraints;
- acceptance criteria and known risks.

Kimi confirms the handoff is complete before editing. Missing scope, contradictions, or unsafe assumptions go into `OPEN_QUESTIONS.md`, and execution pauses unless the owner resolves them.

## 5. Execution

Kimi owns the implementation.

Rules:

- Keep the change inside the approved scope.
- Prefer existing project patterns and helpers.
- Add or update tests at trust boundaries and behavior changes.
- Regenerate dependent artifacts from source, never by hand.
- Run the narrow gates first, then the broader gates the change touches.
- Do not mutate git unless the owner explicitly asks.

Kimi's completion report names exact files, commands, results, and remaining risks.

## 6. Review

Claude reviews the implementation against the handoff and repository quality bar.

Findings are ordered by severity:

1. structural regressions or broken contracts;
2. correctness, security, privacy, accessibility, or reproducibility defects;
3. missing tests or verification evidence;
4. missed simplifications and unnecessary scope;
5. naming, readability, and local consistency.

A review response must distinguish required changes from suggestions. It must not request new product scope unless the owner approves a new design cycle.

## 7. Close

Kimi resolves required findings and reruns the gates. Claude confirms closure in the review file. The session owner commits the finished design, review, implementation, and generated artifacts.

## Conflict avoidance

- Claude writes under `designs/`; implementation edits stay in the approved code surface.
- Kimi writes the implementation summary in the handoff or a sibling execution note.
- If both agents need the same file, the owner serializes the turns or assigns ownership explicitly.
- If a live experiment, paid provider call, deployment, or git mutation is required, the owner approves it separately.

## Escalation

Stop and escalate when:

- the design conflicts with committed evidence or public copy;
- implementation reveals an invalid assumption in the design;
- a gate cannot be run locally without paid access or external state;
- a rollback or destructive action would be needed;
- the agents disagree on architecture after one revision round.

The owner decides whether to revise the design, narrow the scope, or discard the change.
