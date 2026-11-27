# Orchestrator message — push and deploy grade pass 5 (HOLD until preconditions are met)

Do not push, merge, or deploy until **every precondition below is true**. If any is false, stop and report.

## Preconditions
1. Kimi's commit for `09-kimi-08-grade-fix.md` (`docs(review): record owner decision to keep 08 at 8.8`) is on `wave8-articles-truthfulness-2026-11-25`. The phase-7 08 row reads 9/9/8/9 → 8.8.
2. Kimi's commit for `10-kimi-09-test-approval.md` (`test(09): …`) is on the branch. Five runs of `projects/09-agentic-workflows` recorded in `phase-6-result.md` with exit codes.
3. `uv run mypy libs projects apps` exits 0 on the branch head.
4. The branch's `git status` shows only `scratchpad/` untracked.
5. **Owner approves the fast-forward of `main` and the push.** This has not been given yet.

## Steps (once the preconditions hold)
1. Confirm the branch head and that `main` is at `765d175f`.
2. Fast-forward `main` to the branch head. Do not force-push. Do not rewrite history. Do not amend.
3. Push `main` and the branch to origin.
4. Deploy with the repo's standard process. If the process isn't documented in the repo, stop and report.
5. After deploy, confirm `/health` shows the new commit sha.
6. Confirm the project 13 page has no "champion" wording and shows the v2 LightGBM. Confirm the project 15 diagrams render.

## Commits in this release (pass 5 and its records)
- `51997c87` E9 blend refit (02)
- `b7568ffb` pass-4 docs handoff
- `606587f8` 01 final_v4 and judges
- `405d579c`, `a46cf5f3`, `96b25cbb`, `34f59274`, `4e20a2b4` 12→13 v2 promotion
- `935d34ed`, `f88b259d` 13 parity disclosure
- `e5d61f13` 01 mypy fix
- `53486d6f` pass-5 review records
- plus the two pending Kimi commits from preconditions 1 and 2

## Do not include
- Any model co-author trailer in any commit or PR body.
- The gitignored `projects/08-inference-serving/data/bench_run_repeat.json`.
- The `scratchpad/` folder.

## Known open items to report, not block on
- Project 15's 9.3 depends on the orchestrator's browser check of its five diagrams. Until that check runs, 15 is 9.0.
- Project 01 is 8.8: T is capped at 8 because the replication F1 0.8466 disagrees with the committed 0.9091.
- Project 08 is 8.8 on one host, owner-accepted.
- Project 09's deadline tests were flaky under load before the change in precondition 2.

## Report back
Branch head, `main` head after fast-forward, push result, deploy result, the `/health` sha, the browser-check result for 15, and any step not completed.
