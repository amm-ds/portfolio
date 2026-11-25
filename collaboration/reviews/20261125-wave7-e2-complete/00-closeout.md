# Wave 7 closeout: dynamic pricing E2-7 through E2-9 and S-R

Date: 2026-11-25  
Executor: Kimi Code  
Branch: `wave7-dynamic-pricing-rl-2026-11-25`  
HEAD: `b9d37131b07fa1dbc1eb20f3cab441d0e65ebab4`  
State: **implementation, sealed evaluation, article, and registrations complete; ready for owner + Claude review**

## Outcome

E2-7 used the intact winning checkpoint and did not rerun after the owner committed
the frozen data inputs. E2-8 consumed each sealed set exactly once. E2-9 and S-R
are complete. No commit, push, or merge was made.

The primary result is negative and is reported without qualification as a win:
masked PPO reaches `0.5120026324` mean normalised profit on the `1,000`-episode
sealed test, while locked comparator B1 reaches `0.5216981845`. Relative lift is
`-1.8584600073%`; the paired episode-bootstrap difference is `-0.0096955521`
with 95% CI `[-0.0114372255, -0.0079979385]`, `2,000` resamples, seed `42`.
**P1 fails.** **P2 passes:** every executable policy has zero violations on every
test episode. P3 remains context only.

The practical lesson is narrow and useful: under the assumed Bijmolt elasticity
prior, static `1.30×` pricing captures margin that the learned adaptive policy
does not recover. PPO beats B0/B2/B3, but that does not satisfy the primary gate.
This is simulator evidence only, not observed retail revenue or a deployment case.

## Training and selection evidence

- `MaskablePPO` with `HistoryEncoder` and `SubprocVecEnv(8)`; `3,000,000`
  requested steps for each seed `0`, `1`, and `2`.
- Validation mean over `300` episodes: seed 0 `0.5125362780`; seed 1
  **`0.5143695548` — selected**; seed 2 `0.5142881252`.
- Every seed had zero validation violations and received action masks at prediction.
- Only `reports/models/ppo_seed_1.zip` remains; non-winning checkpoints were deleted.

## Single sealed evaluation

One invocation ran B0–B3, selected masked PPO seed 1, and fluid UB on the test set,
then both stress sets. It completed in `305.366` seconds task wall time. No second
sealed invocation occurred during figure generation, documentation, or gates.

| Policy | Mean normalised profit | 95% mean CI | Fluid-bound share | Violations |
|---|---:|---:|---:|---:|
| B0 | 0.4105275941 | [0.4051643792, 0.4159915542] | 77.5863% | 0 |
| B1 | **0.5216981845** | [0.5160160446, 0.5276627236] | **98.5967%** | 0 |
| B2 | 0.3978450353 | [0.3932762733, 0.4021747278] | 75.1895% | 0 |
| B3 | 0.5028383951 | [0.4969648798, 0.5089785164] | 95.0323% | 0 |
| RL seed 1 | 0.5120026324 | [0.5064805404, 0.5176742709] | 96.7643% | 0 |
| UB | 0.5291234796 | [0.5236914599, 0.5347582840] | 100.0000% | n/a |

Secondary sealed comparisons for RL: `+24.7182%` versus B0, `+28.6940%` versus B2,
`+1.8225%` versus B3, and `-1.8585%` versus B1. At stress mean `-1.5`, RL/B1/B3
means are `0.5449778795/0.5648814659/0.5356181884`; RL is `-3.5235%` versus B1
and `+1.7475%` versus B3. At mean `-3.5`, they are
`0.4817091483/0.4836677575/0.4753169064`; RL is `-0.4049%` versus B1 and
`+1.3448%` versus B3. Neither stress result changes P1.

Protocol evidence:

- Pre-registration SHA-256 remains
  `c94f0f97c37afd2788760356b31d89de8fb3d1790b9fc0685bdbcc15bd9cf627`.
- `reports/sealed_access.json` has exactly three ordered `seal_read` rows, one for
  test and one per stress set, with the frozen spec hashes.
- `reports/test_episodes.json` is `1,297,936` bytes, within the git budget, and
  includes all rows plus 91-day B1/RL traces for fixed-seed episodes 89, 654, 773.
- `git grep -c "/Users/" -- projects/15-dynamic-pricing-rl` returns no matches.

## E2-9 deliverables

Generated without another policy evaluation:

- `reports/figures/profit_vs_baselines.{json,html}`
- `reports/figures/price_traces.{json,html}`
- `reports/figures/bound_share_by_rho.{json,html}`
- `reports/figures/calibration_overview.{json,html}`
- `reports/report.html`, built with `ReportBuilder`, with four embedded figures and
  explicit P1-fail/P2-pass text
- `README.md`, `DESIGN.md`, `portfolio.yaml`, and eight-section `story.yaml`
- Four documentation PNGs under `docs/assets/projects/15-dynamic-pricing-rl/`

The story has a 218-character short version, five lifecycle roadmap cards (four
shipped and one next), all four captions, and 1,720 main-thread words. Story lint
finishes with **0 errors and 0 warnings**. Limits explicitly cover simulator-only
results, the Bijmolt et al. (2005) assumption rather than causal M5 elasticity,
and absent reference-price and substitution effects.

## S-R registrations

Completed card copy/tags, About counts (`14` / `fourteen`), root README and docs
index rows, the new docs page, M5 data-card "Used by", CI/nightly matrix rows with
`--cov=src`, headline extraction/tests, and all four figure exports. Generators
produced a 14-project registry, 14-story short-copy map, and 28-route manifest.
Their `--check` modes all pass.

A temporary API on port 8015 returned `14` projects and the complete project-15
card. Port 8000 was already occupied by a pre-existing process, which was not
touched. The temporary server was stopped after verification.

The figure export script also regenerated unrelated PNGs that were clean before
that command. Those files were restored byte-for-byte from HEAD; only the new
project-15 PNG directory remains. Other concurrent source/story/report changes,
including `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/`,
were not reverted or edited by this closeout.

## Gate summary

| Gate | Final result |
|---|---|
| Project pytest with coverage | **36 passed**; 52% project coverage; documented Gymnasium warnings only |
| Full offline Python suite | Red: two unrelated failures in projects 02 and 10; project 15 passed; combined library coverage 97.14% |
| Ruff + format | Passed; 949 files formatted |
| mypy | Passed; 266 source files |
| import-linter | Both contracts kept; 249 files, 891 dependencies |
| Story language | 14 stories; **0 errors, 0 warnings** |
| Docs/copy/demo/headline checks | Passed; 42 short-copy surfaces; 13 headline claims |
| Figure budget/axes | Passed; pre-existing warnings in projects 01/03/10 only |
| Generator checks | Static registry, story short copy, and routes current |
| MkDocs | `mkdocs build --strict` passed |
| Web | 56 files / **754 tests passed**; ESLint, TypeScript, Vite build passed |
| Absolute-path and sealed-access checks | Passed |
| Release-artifact check | Red on pre-existing non-object `_meta` in projects 02 and 09; no project-15 error |
| Metrics lineage check | Red for unrelated stale 01/02/09/11 artifacts and expected uncommitted project-15 lineage |

## Known provenance limitation

Project 15's metrics stamp points to HEAD `b9d37131`, but the new
`reports/metrics.json` payload is intentionally uncommitted. Therefore
`stamp_metrics_meta.py --check` correctly reports that the artifact did not exist
at that commit. The owner should review and commit the metrics payload, then rerun
`scripts/stamp_metrics_meta.py` for project 15 and commit the refreshed `_meta` as
required by the repository workflow. No commit or fake timestamp was used to hide
this state.

The global release/lineage checks also report pre-existing or concurrent issues in
projects 01, 02, 09, and 11. Those artifacts were left untouched. The full offline
suite has two unrelated failures: project 02's ensemble quote no longer matches its
concurrently rewritten story, and project 10's multi-arm figure test expects labels
where the concurrently modified figure supplies numeric values. Project 15 passed
within that run; neither unrelated project was changed to repair its failure. All
project-15 and registration gates are green, with the owner-commit lineage step
above remaining open.

## Review entry points

- `projects/15-dynamic-pricing-rl/reports/metrics.json`
- `projects/15-dynamic-pricing-rl/reports/test_episodes.json`
- `projects/15-dynamic-pricing-rl/reports/sealed_access.json`
- `projects/15-dynamic-pricing-rl/reports/report.html`
- `projects/15-dynamic-pricing-rl/story.yaml`
- `projects/15-dynamic-pricing-rl/README.md`
- `projects/15-dynamic-pricing-rl/DESIGN.md`
- `collaboration/designs/20261124-next-experiments/04-execution-notes.md`

Working tree remains uncommitted for review. No push or merge was performed.
