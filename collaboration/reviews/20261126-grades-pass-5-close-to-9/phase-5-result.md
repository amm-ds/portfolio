# Phase 5 result — copy and figure close-out sweep

Date: 2026-11-26. Branch: `wave8-articles-truthfulness-2026-11-25`.
Method: verify each plan item against the tree; fix only gaps. Most items
were already satisfied by pass-4 phases and the docs handoff.

## Per-project findings

| project | item | status |
|---|---|---|
| 03 | 0.527 collision wording | verified — disambiguated at story.yaml:7 and :164 ("a different metric from the minute-level PR-AUC (also 0.527 by coincidence)") |
| 03 | no "champion" in figure titles | verified — scan of all committed figure JSON titles/data: zero occurrences (range_pr names IsolationForest; telemetry says served-model) |
| 04 | broken sentence | fixed in the docs handoff commit (`b7568ffb`) |
| 04 | paired cascade CI in copy + figure | verified — E6's CI [−0.0081, +0.0060], McNemar p = 1.000 in story/README/docs; error bar on llm_cascade_comparison |
| 05 | headline-first titles; threshold-selection note | verified — bootstrap_ci title leads the finding; copy carries "threshold re-selected each time… does not measure selection instability" |
| 06 | 5-vs-8 count | verified — no 8-of-56 remnant; figure title, story, docs all say 5 (ties excluded, −0.005% threshold) |
| 07 | E2 CI in copy; coverage source | verified — served-model CI −1.841 [−2.338, −1.258] in story/README/docs/MODEL_CARD; `analysis.p90_coverage` in metrics.json |
| 09 | 17/19 on four surfaces | fixed in the docs handoff commit (short_version, docs index, root README, docs page) |
| 10 | CI in metrics.json; 12.03 wording | verified — E1's `analysis.ci` bit-identical to 0c01c45d and gated; the two-interval wording explains the per-arm vs two-arm resampling ("read the ranking as weak either way") |
| 11 | non-finding titles | verified — Phase C titles state findings (×19.2/×14.9, slopes 0.73/0.63, 1,520 MB) |
| 01 | Phase 2 copy | committed in `606587f8` (replication F1 0.8466 disclosed, weak 3B cross-family read labelled) |
| 02 | E9 copy + stale interval clause | committed in `51997c87` + `b7568ffb` (short_version now "level 95% CI [0.5588, 0.6974]") |
| 12/13 | v2 promotion copy | committed in Phase 4 (`34f59274`): corrected MLP worse (27.16 vs 25.43), corrected LightGBM better (23.76 vs 25.37) and served; 13 names LightGBM, v1 kept as history |

## Gaps found and fixed in this sweep

- `projects/01-rag-agent/scripts/grade_final_v4_rerun.py` failed repo-wide
  mypy (unannotated mixed-type dict + name collision) — fixed
  (`dict[str, Any]` annotation, renamed to `cross_family`); 01 suite still
  190 passed. (The 2c prompt's gate list ran `mypy src` only; the Phase 6
  sweep caught it — working as intended.)

No other gaps. Short copy and static registry regenerated per repo rules
during the phase commits.
