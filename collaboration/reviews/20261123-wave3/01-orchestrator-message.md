# Orchestrator message: Wave 3 state and the erratic-challenger call

Date: 2026-11-23 · From: Kimi Code · Branch: `phase0-infra-2026-11-22` (nothing committed)

## Delivered and green (uncommitted; ready for your review-and-commit pass)

- **Roadmaps**: all 12 stories (02–13) rebuilt on the 5-card lifecycle arc
  (4 shipped + 1 next, contract-verified programmatically).
- **02 headline reconciliation**: every copy surface now matches the owner's
  10-origin working-tree metrics (0.6211 champion, −30.4%, 0.95/0.00/0.05
  weights, 9-selection protocol, updated pinning tests). The two pre-existing
  `check_headline_numbers` findings are **cleared — 0 findings**. Full 02 test
  suite passes.
- **UI card green standard**: every true card shares the 3px `--card-accent`
  left rail; dark unchanged; 753 web tests + build green.
- All repo gates green (lint 0 errors, short-copy single-sourced, docs,
  demo-contract, registries). Closeout:
  `collaboration/reviews/20261123-wave3/00-closeout.md`.

## Situation: wave-34 erratic challenger (needs the owner call)

Design, harness, cache, CLI, and tests are complete. Calibration on the first
selection origin finished: **champion 0.7409 vs routed 0.8683 — a large
regression**, and the erratic win-rate vs the naive floor dropped (0.866 →
0.837). The stratum-restricted Huber arm is worse on its own target stratum,
consistent with the wave-33 spike-weight rejection (0.6235 vs 0.6211).

The full 9-origin screen runs as **one sequential process** (the config that
survived the 13 h calibration; a 4-way parallel attempt died silently in
concurrent panel prep — parallel by origin needs a shared prep, a later
improvement). ETA ~4 days; origin 1877 replays from cache. Per the promotion
rule it will not pass: the screen requires the routed arm to beat the champion
on the selection pooled mean, and a ~17% relative deficit on origin 1 will not
be overturned by the remaining origins under an identical recipe.

**Decision (resolved 2026-11-24): stopped by owner.** Wave-34 is recorded as
*rejected on the origin-1 calibration signal, screen stopped by owner
decision*: champion 0.7409 vs routed 0.8683 on 2016-03-20, erratic win-rate
down 0.866 → 0.837. The champion (0.6211) stands; the test origin was never
read; the origin-1 record and the forecast cache are preserved under
`reports_m5_full/` and `data_m5/raw/.cache/full_forecasts/`. The roadmap `next`
card names the follow-up gate.

## Notes

- `data_m5/raw/m5/datasets/m5.zip` was missing; re-fetched from the canonical
  source, sha256 matches the Phase-0 pin exactly.
- `reports_m5_full/demo_payload.json` still carries old pooled-arm per-series
  forecasts; full sync needs a wave-32 catalog rerun (~3 h) — flagged in the
  closeout, no gate reads it.
- README's "Validation" bullet still describes a 3-origin validation harness
  (pre-existing, unrelated to the headline protocol).
