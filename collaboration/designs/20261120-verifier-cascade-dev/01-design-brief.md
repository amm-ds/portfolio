# Design brief: verifier cascade, DEV-only calibration (project 01)

Date: 2026-11-20
Designer: Claude Code
Owner: amm-ds
Status: approved (owner, 2026-11-20): offline DEV-only calibration, $0 hosted. Hosted generation pass and hand-labeling are NOT approved.
Related artifacts: `collaboration/designs/20261119-rag-verifier-challenger/` (Phase 1 FAIL), `collaboration/reviews/20261119-rag-verifier-challenger-report/00-report.md`, `verifier-challenger-2026-11-20` branch `reports/verifier_challenger/predictions.jsonl`, `projects/01-rag-agent/data/calibration/verifier_split.json`

## Problem

The single-threshold MiniCheck verifier failed one criterion: false rejection on supported claims was 0.143 on TEST against a 0.10 cap. Its false acceptance of unsupported claims was 0.041, far better than the hosted judge's 0.40. The trade-off is in the threshold. A single cut cannot separate the classes cleanly, because the score distributions overlap.

A three-band cascade keeps the confident MiniCheck decisions and sends the uncertain middle to a second judge. That targets both criteria at once, at no new hosted cost.

## Context and evidence

| Claim | Evidence path | Why it matters |
|---|---|---|
| MiniCheck single threshold: FA 2/49 = 0.041, FR 7/49 = 0.143 on TEST | `reports/verifier_challenger/metrics.json` | The cascade must reduce FR without raising FA |
| Threshold 0.9410 chosen by DEV accuracy, which over-rejected supported claims | same | The rule was too blunt; a band rule is the fix |
| Per-claim MiniCheck scores for all 194 claims are committed | `reports/verifier_challenger/predictions.jsonl` | No MiniCheck re-run is needed |
| Local judge per-claim verdicts are NOT committed (aggregate only) | `reports/judge_calibration/results.json` limitation | The middle band needs a fresh local judge run on all 194 claims |
| TEST was already used for the single-threshold report | verifier challenger report | TEST cannot select the cascade; it is descriptive only |
| Shipped verifier accepted 81 of 82 judged claims on sealed_v2 58 | `reports/sealed_v2/metrics.json` detail.heldout.verify | Confirms the verifier, not retrieval, is the weak point |

## Goals and non-goals

Goals:
- Choose cascade thresholds on DEV only, by 5-fold cross-validation, under a rule fixed before any scoring.
- Report one descriptive TEST reading for the chosen rule, marked as a second use of TEST.
- Report whether the cascade meets the cap on cross-validated DEV, and say plainly if it does not.

Non-goals:
- No hosted calls, no generation pass, no hand-labeling.
- No change to the production verifier, the agent, copy, or headline numbers.
- No threshold scan on TEST, and no re-scoring of TEST to find a better rule.

## Constraints

- Cost: $0 hosted. The local judge runs on the owner's machine via Ollama, if Ollama is running; if not, stop and report.
- Splits: DEV is `verifier_split.json` dev rows only (96 claims: 48 supported, 48 unsupported).
- Gate values: the original 0.10 caps on both FA and FR. The Sonnet review proposed tightening FR to 0.08; the owner has not chosen, so this plan keeps 0.10 and flags 0.08 as a sensitivity read only.

## Options

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| A. Three-band cascade, MiniCheck plus local judge on the middle band, thresholds by DEV CV | Targets both criteria; $0 hosted; reuses committed MiniCheck scores | Middle band depends on a 3B judge that is noisy (kappa 0.55); may not clear the cap | Recommended |
| B. Keep single threshold, lower it to hit FR cap | Simplest | Raises FA; repeats the trade-off already measured | Not recommended |
| C. Extractive fallback for refused answers | Could cut false abstention | Needs hosted generation to measure; not an offline step | Later, if A passes |

## Recommendation

Option A, run offline on DEV. If the cross-validated rule finds no band meeting both caps, the cascade fails and the project closes with the measured results. There is no re-scan.

## Acceptance criteria

- [ ] Rule frozen in the handoff and its sha256 recorded before any cascade scoring.
- [ ] Local judge verdicts on all 194 claims cached once, with the prompt and model recorded.
- [ ] 5-fold CV on DEV over a fixed grid; chosen band is the qualifying one with the lowest deferred share, ties to lower FA.
- [ ] Final cascade thresholds fitted on full DEV; reported.
- [ ] One descriptive TEST reading reported, labeled as second use.
- [ ] Gates run and reported.

## Rollback and failure behavior

- Failure modes: Ollama not running; local judge output not parseable on some claims; no band qualifies.
- Observability: every claim's MiniCheck score, local verdict, band, and final decision written to a predictions file.
- Rollback: delete the new report folder. Nothing in production or the app changes.

## Open questions

- Owner: keep 0.10 FR cap (this plan) or tighten to 0.08 before the rule is frozen? This plan uses 0.10 unless you say otherwise.
- Owner: is Ollama running locally with `qwen2.5:3b` available for the middle-band judge?
