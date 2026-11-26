# Phase 4 approval — project 12 option B, LightGBM served under v2

Date: 2026-11-26. Branch `wave8-articles-truthfulness-2026-11-25`.

## Owner decision
Option B is approved: promote v2 as the project 12 headline and regenerate project 13 from v2. The owner has accepted that LightGBM is the better model under v2 and will be the served model in project 13. This resolves the Phase 4 step 5 stop in `04-revised-execution-plan.md`.

Phase 3 numbers (`phase-3-result.md`), for reference:
- v1 reproduction exact: MLP 25.4316, LightGBM 25.3732.
- v2, three runs, bit-identical: MLP 27.161, LightGBM 23.764, seasonal naive 72.976 (matches E4).
- Validation selects LightGBM (31.94) over MLP (35.13).

## Scope
Phase 4 only, as written in `04-revised-execution-plan.md`, with step 5 now approved. No new experiments. No hosted calls. No changes to project 01, 02 or 08.

## Steps (commit each as its own commit, no co-author trailer)
1. Fix the `_meta` dict literal in `projects/13-model-serving/src/model_serving/report.py` (own commit). Gate: 13 test suite passes.
2. Promote v2 artifacts into project 12. Keep v1 under `previous_runs.v1` in `metrics.json` (additive). Restore any `_meta` or lineage field that changes beyond the intended change.
3. Regenerate project 13 from v2 with LightGBM as the served model:
   - reproduction target = v2 LightGBM test MAE (23.764) with the v2 MLP shown as the comparison;
   - ONNX parity for LightGBM at 1e-4; stop if it fails;
   - images and load bench regenerated.
4. Copy updates for 12 and 13 in one commit:
   - 12: "v2 fixes two disclosed defects; v1 remains for comparison and moved by the change in LightGBM and MLP. The corrected MLP is worse (27.16 vs 25.43); the corrected LightGBM is better (23.76 vs 25.37)."
   - 13: name LightGBM as the served model; drop any copy that says the MLP is served; keep "champion" out of reader-facing copy.
   - Re-key the headline and reproduction gates in the same commit.
5. Gates: story lint, short copy, story short, static registry, headline numbers, docs, mkdocs strict, figure axes and budget, demo contract, project 12 and 13 suites, `git diff --check`. Record exit codes in `phase-4-result.md`.

## Stop and report
- Any ONNX parity or reproduction gate fails.
- Any committed number changes beyond the v1 to v2 change in 12 and 13.
- Anything needs hardware or data outside this plan.

## Not part of this approval
- Phase 2 answer regeneration (about $1 for re-running the 120 final_v3 questions). This still needs the owner's own OK. Until then, the cross-family judge work may stop before generation.
- Fast-forward of `main`. Not approved.
- E9 (02 refit) is still running. Do not touch its in-flight files.

## Report back
Result file `phase-4-result.md`, commit hashes, gate exit codes, any number that changed and why, and the 12 and 13 grades before and after.
