# Fix: move the 09 correction sentence to the end of its bullet

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code
Status: approved
Source: review of `collaboration/reviews/20261119-xgb-naming-and-design-note/00-report.md`

## Problem

In `projects/09-agentic-workflows/DESIGN.md`, the correction sentence added under the 2026-10-18 bullet interrupts the original sentence. Lines 181–183 read:

- line 181: `(8 unplanned calls); Critique now audits TOOLS USED against the PLAN and`
- line 182: `Correction (2026-11-19): the "8 unplanned calls" count has no committed artifact behind it ...`
- line 183: `the Execute node records tools per visit (superseded attempts no longer`

## Required change

1. Remove the correction line (line 182) from its current position.
2. Insert it at the end of the same 2026-10-18 bullet, after the last line of that bullet and before the next bullet begins. Keep the same bullet indentation and the same text.
3. Do not change any other line. The original sentence must read unbroken again.

## Verification

- `git diff -- projects/09-agentic-workflows/DESIGN.md` shows one added line, at the end of the 2026-10-18 bullet, and no other change.
- Read the bullet and confirm the original sentence is unbroken.

## Gates

No code or story change. Run only:

```bash
uv run python scripts/check_docs.py
```

Report the actual output. Do not commit. Do not run any hosted call or any Q3b, Q3c or Q4 item.
