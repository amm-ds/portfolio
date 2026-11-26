# Grade pass 4, Phase D (experiments): result

Branch: `wave8-articles-truthfulness-2026-11-25`.

## Commits

- `3b27961b` refactor: D0 — analysis moved out of `_meta` (7 projects +
  API/web consumers + repo guard test). No artifact changes.
- `5483124f` feat: D1 — CPU experiments E1–E5.
- `9d464028` chore: restamp `_meta` lineage for 07 10 (only the two
  payload-changed artifacts; the other 15 keep valid earlier stamps).
- `94345c4e` feat: D2 — hosted experiments E6–E8. Total hosted spend
  **$0.41 of the $5.00 cap**.

## D0 (prerequisite)

`_meta` is now reserved for the provenance stamp; analysis lives under a
top-level `analysis` key in 01/02/04/05/07/10/12. Readers that need data
only a re-run can restore fail loudly. Consumers updated:
`_headline_metric` (API) and `pickHeadlineMetric`/`MetricsTable` (web)
prefer `analysis.champion` (legacy `_meta.champion` fallback) and never
treat `analysis` as a run. Guard: `scripts/tests/test_no_meta_subscript.py`.

Known follow-ups (not in D0 scope): `13 report.py` writes a `_meta`
dict-literal (same clobber bug, not in the D0 list); the API fallback and
web `pickHeadlineMetric` should be re-checked after any future re-run that
adds `analysis.champion` to more projects.

## D1 outcomes (all reproduction gates passed; no stop condition hit)

| Exp | Project | Result | Headline impact |
|---|---|---|---|
| E1 | 10 | CIs persisted to `analysis.ci`, bit-identical to `0c01c45d` ([717.58, 4766.66] / [−13124.81, −5807.77]); demo payload regenerated | none (gate now reads metrics.json) |
| E2 | 07 | Served-model CI: −1.841 MAE, day-block [−2.338, −1.258], zone-cluster [−2.464, −1.266]; xGB vs served −0.190 [−0.265, −0.115]; `analysis.p90_coverage` = 0.90795 persisted. MAE bit-exact | admission replaced by measured CIs |
| E3 | 05 | Committed split reproduced exactly ($601/$1,035, t=0.175). 20 splits: median −$391.5, 95% range [−$438.6, −$340.4], all below zero; committed split inside, favorable side. New `repeated_splits.json` + rug strip on bootstrap_ci | copy adds the 20-split range |
| E4 | 12 | Reproduction exact (25.4316, diff 0.0). **Corrected variant is significantly WORSE for the served MLP: 27.16, +1.73 [+0.64, +2.77]**; LightGBM improves −1.61 [−2.98, −0.38]; floor −10.22. Honest-note not triggered | headline keeps committed run; **E12 not started — owner decision** |
| E5 | 03 | NAB scorer vendored (MIT, upstream `ea702d7`, pure Python, no uv.lock change). Null 0 / perfect 100 exact on all three profiles. **Official scores: standard 51.45, low-FP 49.81, low-FN 62.46** — published as-is. Committed 1,609/0.527/[0.230, 0.811] unchanged (recompute-verify baked into the runner) | "NAB score not reported" replaced everywhere |

## D2 outcomes (hosted; meter recorded per item)

| Exp | Project | Spend | Result |
|---|---|---|---|
| E6 | 04 | $0.0206 (stop was $0.036) | Replication F1 0.95189 vs committed 0.95393 (Δ 0.0020 < 0.003). Paired 95% CI [−0.0081, +0.0060] includes zero; McNemar p = 1.000. Copy: gain not distinguishable from zero; error bar on the cascade figure |
| E7 | 09 | $0.3921 (stop was $1.50) | 5 live repeats: **pass^5 = 17/19**, pass@5 19/19; h08 missed the 60 s deadline in 2/5 runs, h01 exceeded the step budget in 1/5. p50/p95 8.9/37.5 s. Honesty rule triggered; copy says pass^5 = 17/19. `live_confirmation_20261119/` byte-untouched |
| E8 | 01 | $0.00 (local) | No cross-family hosted credentials exist (only Moonshot); second judge = local qwen2.5:3b (Alibaba family, digest 357c53fb). Calibration 28/30 vs owner labels (κ 0.86) — passed the 25/30 gate. Claim-level agreement with the committed judge on 147 committed claims: 95.9%, κ 0.92. **Answer-level re-grade BLOCKED: final_v3 answer texts/claims were never committed (only traces)** — the 0.9091 F1 remains single-family at answer level; copy + access log (fifth read, "judge-agreement, no selection") disclose this |

## Owner decisions surfaced

1. **E12 (12→13 option B)**: E4 says the corrected pipeline is worse for
   the served MLP but better for LightGBM (validation would have picked
   LightGBM under the variant). Proceeding with E12 would move every 12/13
   headline. Not started; awaits owner.
   - *Addendum 2026-11-26: the owner approved option B with LightGBM served
     (pass-5 `05-phase-4-approval.md`), and accepted the float32 relative
     term in 13's ONNX parity gate on 2026-11-26 — the measured max-abs
     2.65e-4 fails the bare 1e-4 and the gate fails without the term.*
2. **E8 follow-up**: to get a true second-family F1, either persist answer
   texts in a future final_v4 run, or authorize a regeneration run
   (~$1.01, violates "fixed outputs" — owner call).
3. **04 roadmap**: the E6 agent dropped the "Beat every rung with full
   data" next-card to keep the 4-shipped + 1-next convention (flagged for
   reversal if unwanted).
4. **04 dvc.yaml**: the `llm_cascade` stage still declares
   `metrics: reports/llm_cascade.json` though the stage now never rewrites
   it (publish-beside). Cosmetic; adjust if desired.

## Gates at D2 commit

ruff/format/mypy repo-wide clean; project suites 01:186 03:120 04:92
05:69 07:67 09:107 10:71 12:44 pass; scripts/tests 32 pass; web 771 pass;
headline-numbers 24 claims 0 findings; story lint 0 errors (1 known 02
warning until E9 restores the figure); short-copy/story-short/registry/
route-manifest/docs/demo-contract/figure-budget/diagram-fences OK;
figure-axes 1 warning (04 cascade [0,1] bar window with the new scatter
error bar — bars-pin-zero convention, accepted); mkdocs --strict OK;
stamp check OK (17 artifacts).
