# Execution brief — grade pass 4 (owner-approved)

Plan: `00-plan.md` in this folder. Owner decisions below override any open question in the plan.

## Owner decisions

1. **Branch and restamp:** commit on `wave8-articles-truthfulness-2026-11-25`, then fast-forward `main` to it. Restamp the five stale files (projects 01, 02, 09, 11, 12) in a separate commit after the content commit. No push or deploy by you; the orchestrator pushes and deploys.
2. **Accessibility:** approved. Fix the unlabelled scroll region in app code (`apps/showcase-web/src/...markdown.tsx` around line 217, and any other unlabelled scrollable region the axe check reports).
3. **Copy sign-off:** approved. Rewrite the short versions for 01, 03 and 09, and the `README.md:8` claim, as the plan specifies.
4. **Project 02:** drop the superseded sample-series figure (or relabel it so it does not show the superseded blend, whichever the plan rates higher), and run the targeted refit of the two members with the node-bootstrap CI. Budget about 9.4 CPU-hours.
5. **Project 12:** run the sensitivity arm first (1 CPU minute). Recommend the headline option only if the sensitivity result actually moves a headline number, and then regenerate 13 accordingly. Report the outcome whichever way it goes.
6. **Project 08:** accept 8.8. Do not provide a second machine; do not run the matched quantization pair.
7. **Hosted runs:** approved, with a **hard cap of $5** total across all hosted calls. Choose a second-family judge for project 01 within the cap and say which model you used. Publish every re-run beside the committed numbers. Do not replace committed numbers unless a stop rule in the plan says the change is intended.
8. **NAB (project 03):** approved to run the official scorer and publish its result, whatever it shows. Do **not** tune thresholds, select windows, or re-run alternatives to make the score look better. Report it honestly even if it compares poorly.
9. **New experiments in 05 and 07:** approved (20 repeated splits for 05 with threshold re-selection; paired CI and persisted coverage for 07's served model).

## Rules

- No headline number may change unless a stop rule in the plan explicitly allows it. If a re-run moves a number beyond the stated tolerance, stop that item and report.
- Preserve committed evidence. Before any run that rewrites committed files, copy them to the scratchpad; restore any `_meta`, lineage, platform or processor field the run changes beyond the intended change.
- Do not add model co-author trailers to any commit.
- Stop and report, rather than improvising, if any step would exceed the $5 cap, use hardware not described in the plan, or touch the gitignored repeat file in project 08.
- Commit only the approved phases, one commit per phase, with messages that name the phase and the gate results. No push, no merge into anything other than the wave8 branch and `main` fast-forward, no deploy.

## Phases to execute (from `00-plan.md`)

1. **Blockers:** commit pass 2; restamp 01/02/09/11/12; accessibility fix; diagram-fence gate in CI config if its path is allowed in the plan.
2. **Contents and README/docs index:** the reader-facing fixes listed in the plan, including `docs/projects/index.md:14` (0.6161 → 0.6211) and `README.md:8`.
3. **Figures:** retitles from committed data; no compute.
4. **Experiments:** metadata refactor first, then CPU runs (05, 07, 10 persistence, 12 sensitivity, 03 NAB), then hosted runs (01, 04, 09) under the $5 cap, then the 02 refit.

## Reporting

For each phase, write a short result file in `collaboration/reviews/20261126-grades-pass-4-plan/` with: commits made (hashes), files changed, gate exit codes, experiments run with their cost, any number that changed and why, and grades before and after per axis. Final report: a table of 15 projects with before and after overall, plus anything left undone and why.
