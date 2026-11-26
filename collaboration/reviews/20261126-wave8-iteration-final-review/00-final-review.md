# Wave 8 iteration — final review

Date: 2026-11-26 · Reviewer: Claude (design lane) · Branch `wave8-articles-truthfulness-2026-11-25`, HEAD `c05accd0`, Wave 8 tree uncommitted.
No commit, add, stash, checkout, reset, push or merge was run. No refit, forecasting, experiment, training, demo-payload CLI, or hosted/paid call was run.

## 1. Experiments review

| Claim | Evidence | Status |
|---|---|---|
| No catalog refit and no beat-results search this iteration (owner ruled both out). | Owner instruction; `opus-round3/closeout-kimi.md:10,14` (no refit, fallback used) | verified (by instruction and closeout record; no run logs exist to inspect) |
| Demo payload keeps the earlier 0.60/0.10/0.30 blend: pooled WRMSSE 0.6161, bottom WAPE 0.763, zero-day 57.3%, selected on 2 origins. | `projects/02-demand-forecasting/reports_m5_full/demo_payload.json:26` (`groups.test_pooled.convex_ensemble`), `:20245-20251` (`n_selection: 2`, origins 2016-05-08/15/22) | verified |
| Payload is labelled as the earlier blend in the demo. | `ForecastWorkbench.tsx:15-17,302,308,314-316,394-395,424-430`; `panels.tsx:462`; `chartData.ts:57` | verified (vitest 198/198 pass) |
| Current champion committed: convex_ensemble 0.62105, −30.4%, weights 0.95/0.00/0.05. | `reports_m5_full/metrics.json:245,608`; `README.md:95`; `story.yaml:18,159` | verified |
| Full-window routed challenger 0.6235, rejected. | `reports_m5_full/metrics.json:247,293`; `story.yaml:161-163`; `DESIGN.md:774-778` | verified |
| Sample-series figure title now says origin 2016-05-22. | `m5_full_figures.py:79` (`cat_meta["origin"]`); `catalog_meta.json:3`; committed `m5_full_sample_series.{json,html}` title patched in place (figure not regenerated) | verified (text); not verified that a later regeneration is byte-identical |

## 2. Performance review

| Headline | Value | Source | Status |
|---|---|---|---|
| Champion official WRMSSE | 0.6211 (0.62105) | `metrics.json:608` | verified |
| Floor (seasonal naive) | 0.8929 | `README.md:95-100`; `story.yaml:35` | verified |
| Lift vs floor | −30.4% | `README.md:95` | verified |
| Champion bottom WAPE | 0.7623 | `metrics.json:624`; `README.md:95` | verified |
| Champion zero-day accuracy | 57.2% (0.5724) | `metrics.json:626` | verified |
| Best single / storecat | 0.6219 / 0.6225 | `README.md:96-97` | verified |
| Noise band (paired bootstrap) | 0.000644 | `metrics.json:277,291` | verified |

Framing: the top three sit in a 0.621–0.623 field. The champion's edge over the best single fit (0.0008) is about 1.3× the 0.000644 band (`story.yaml:159`). This is a tie-level lead, not a material win; the material result is the 30.4% cut against the floor. The copy states this. Verified.

## 3. Quality review — Wave 8 round-3 closeout

| Item | Evidence | Status |
|---|---|---|
| Fixes 2–5 and 7 of the fix list | `20261126-wave8-round3-closeout-fixes/00-fix-list.md:51` | verified (by rev 3) |
| Item 53: the 38 verbless ". Next, the X (link)." transitions | Spot-read 02:86, 06:55, 06:276, 07:91, 08:270, 09:257, 10:215, 11:279, 12:65 — all now full sentences. A grep for `Next, the … (link).` across 02–13 returns only the 10 section-intro lines below; `; next, the` returns only `15:117`. | verified in the tree |
| Item 53 record | `opus-round3/closeout-kimi.md:21-30,157` still marks item 53 OPEN | not closed — the rewrites are done; the only remaining work under item 53 is flipping the closeout to FIXED with the gate exit codes from this pass (lint 0, short copy 0, story short 0, diff check 0) |
| Optional: 10 verbless section-intro lines | 03:22, 05:19, 06:19, 07:52, 08:59, 09:32, 10:49, 11:19, 12:28, 13:31 | open (optional, owner choice; `00-fix-list.md:54`) |
| Project 15 out of scope | `15-dynamic-pricing-rl/story.yaml:34` (verbless intro), `:117` ("; next, the" splice) | open, out of scope |

## 4. Articles review (projects 02–13)

| Project | Status |
|---|---|
| 02 | Items 1, 3, 4 FIXED (`closeout-kimi.md:41-45`); item 2 fallback taken, owner sign-off pending; demo labels corrected this pass. |
| 03 | Items 20–25 FIXED; "injected anomalies" and conclusions order done (fix list 2, 4); intro 03:22 optional. |
| 04 | Items 5–7 FIXED; `routing.ts` 0.9061 fixture note recorded. No open items. |
| 05 | Items 8–12 FIXED; intro 05:19 optional. |
| 06 | Items 26–28 FIXED; transitions rewritten; intro 06:19 optional. |
| 07 | Items 13–17 FIXED; transitions rewritten; intro 07:52 optional. |
| 08 | Owner option (b) and items 18–19 FIXED; intro 08:59 optional. |
| 09 | Items 29–32 FIXED; intro 09:32 optional. |
| 10 | Items 33–36 FIXED, 37 closed optional; intro 10:49 optional. |
| 11 | Items 38–41 FIXED; intro 11:19 optional. |
| 12 | Items 42–46 FIXED; conclusions reorder done; intro 12:28 optional. |
| 13 | Items 47–51 FIXED; intro 13:31 optional. |

Source: `opus-round3/closeout-kimi.md:37-161`, re-checked against the tree for items 53 and 2. Other per-item statuses are taken from the closeout and the prior rev-3 review, not re-verified line by line in this pass.

## 5. Owner decisions still open

1. Project 02 fallback sign-off: approve the earlier-blend disclosure (payload 0.6161 kept and labelled; champion 0.6211 shown beside it), or order a refit later. `closeout-kimi.md:31,43`.
2. Whether to commit the Wave 8 tree (97 files changed, uncommitted, on `wave8-articles-truthfulness-2026-11-25`).
3. Optional: fix the 10 section-intro lines for consistency.

## Gates (this pass)

lint_story_language 0 · check_short_copy --check 0 · gen_static_registry --check 0 · gen_story_short --check 0 · check_headline_numbers 0 · git diff --check 0 · vitest (ForecastWorkbench, diagramSpecs, chartData) 0 · tsc --noEmit 0 · eslint (touched) 0 · ruff (m5_full_figures.py) 0. Full suite (pytest, npm build, mkdocs) not re-run this pass.
