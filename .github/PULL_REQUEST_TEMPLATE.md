<!--
Thanks for the contribution. This template mirrors the engineering playbook:
design reasoning is as reviewable as the code.
-->

## Summary

<!-- What does this change and why? Link the issue/design doc. -->

## Design questions (playbook §Definition of Done)

- What alternatives were considered and rejected, and why?
- What is the rollback path if this change misbehaves in `dvc repro`?
- Does any contract change here (pydantic schemas, config keys, eval metrics)?
  If yes, which downstream projects/consumers are affected?

## Checklist

- [ ] `make test` green locally (ruff, mypy, pytest with coverage gates)
- [ ] No secrets, raw data, or generated artifacts committed
- [ ] Config constants live in pydantic models, not in logic
- [ ] Tests added/updated; hypothesis property tests for new validators
- [ ] Docs updated (README / DESIGN.md / ADR if a decision changed)
