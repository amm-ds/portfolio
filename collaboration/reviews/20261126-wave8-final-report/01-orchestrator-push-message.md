# Orchestrator message — push Wave 8 to main and production

Reviewer verdict (Opus, `00-report.md`): **YES WITH NOTES.** All 12 articles (projects 02–13) match committed artifacts. No HOLD blockers. All gates passed at commit `ebb889cf`.

## Instruction

1. Confirm the current state:
   - `git rev-parse --short HEAD` is `ebb889cf`.
   - `git status --short` shows only untracked review folders under `collaboration/reviews/20261126-wave8-final-report/` (this report is not part of the commit).
   - Projects 01 and 15 have no diff against `c05accd0`.
2. Push branch `wave8-articles-truthfulness-2026-11-25` to origin.
3. Bring the change to `main` using the repo's usual release path (PR or fast-forward, per the repo's own rules). Do not force-push. Do not rewrite history.
4. Deploy to production using the repo's standard deploy process. If that process is not documented in the repo, stop and report instead of guessing.
5. Do not add a model co-author trailer to any commit or PR body.

## Notes the owner should see (not blockers, per the reviewer)

- Project 13 calls its model "champion" in nine places. Project 12 says "without a champion label". Wording fix is queued for a small follow-up pass.
- Project 02 does not explain why the demo's earlier blend was replaced (2 selection origins vs 9). Explanation fix is queued for the same follow-up pass.
- Project 08 and project 13 cost the same laptop at 100 W and 65 W. Both label it an assumption, so the cost lines are not directly comparable.
- Project 10's confidence intervals appear only in `report.html`, not in `metrics.json`.
- Project 03 has one leftover run-on sentence at `story.yaml:115`.
- Project 12 discloses a feature-pruning bug that remains in the committed run.

## Report back

Send the new `main` commit hash, the production deploy result, and any step that could not be completed.
