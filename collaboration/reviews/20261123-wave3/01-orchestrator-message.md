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

The full 9-origin screen is **sharded across 4 parallel workers right now**
(origin 1877 cached; shards cover 1884–1933; ETA ~14–20 h). Per the promotion
rule it will not pass: the screen requires the routed arm to beat the champion
on the selection pooled mean, and a ~17% relative deficit on origin 1 will not
be overturned by the remaining origins under an identical recipe.

**Decision needed**:
(a) Stop the shards now; record wave-34 as *rejected on the origin-1
calibration signal, screen stopped by owner decision* — my recommendation; or
(b) let it run overnight for the full 9-origin measured-and-rejected record
(test origin untouched either way; verdict lands in
`reports_m5_full/erratic_challenger.json`).

## Notes

- `data_m5/raw/m5/datasets/m5.zip` was missing; re-fetched from the canonical
  source, sha256 matches the Phase-0 pin exactly.
- `reports_m5_full/demo_payload.json` still carries old pooled-arm per-series
  forecasts; full sync needs a wave-32 catalog rerun (~3 h) — flagged in the
  closeout, no gate reads it.
- README's "Validation" bullet still describes a 3-origin validation harness
  (pre-existing, unrelated to the headline protocol).
