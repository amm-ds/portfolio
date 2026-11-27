# Design brief: grade pass 6, project 15 (RL pricing) and the review gaps

Date: 2026-11-27
Designer: Claude Code
Owner: amm-ds
Status: approved (2026-11-27; owner accepted the recommendations below)
Related artifacts: `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-7-result.md`; Opus review of project 15 (2026-11-27, delivered in-session); `projects/15-dynamic-pricing-rl/`

## Problem

Project 15 is recorded at 9.3 (9/10/9/9) in the pass-5 grade table. An independent Opus review of the article and results scores it at 9 / 9 / 9 / 8.5 (8.9 overall) and finds the gap is real:

- Results is 9, not 10. The negative result rests on one retained seed (seed 1). Nothing shows how the paired RL − B1 gap varies by elasticity or stock pressure, so the reader cannot see why the fixed price wins.
- Best practices is 8.5. `MODEL_CARD.md` is an unfilled 264-byte stub, and the story has no code excerpt. Every other story with a model card has one.
- Several sentences claim more than the evidence supports (one sealed read, not "repeated checks"; "proves safe behaviour"; "learned well").

Separately, the owner asked for scores to improve in general. Only project 15 has had a gap review so far. Projects 01 and 08 are capped by things copy cannot fix (see Non-goals). The other twelve projects have never been reviewed against the 9.5 bar, so this round does not claim gains for them.

## Context and evidence

| Claim or constraint | Evidence path | Why it matters |
|---|---|---|
| Headline numbers match the committed metrics | `projects/15-dynamic-pricing-rl/reports/metrics.json` | Copy must trace to this file |
| One sealed read per set; three reads total | `projects/15-dynamic-pricing-rl/reports/sealed_access.json` | New analysis must not reopen the sealed test sets |
| Per-episode test results exist | `projects/15-dynamic-pricing-rl/reports/test_episodes.json` (1.2 MiB) | Source for the paired-gap breakdown |
| Validation: B1 0.5225 vs RL seed 1 0.5144 | `reports/baselines_val.json`, `reports/ppo_val.json` | Disclosure: the loss was visible on validation |
| Only seed 1 retained; seed spread on validation 0.5125–0.5144 | `story.yaml` training section; `README.md` lines 96–97 | Limit to state |
| `MODEL_CARD.md` is the template stub | `projects/15-dynamic-pricing-rl/MODEL_CARD.md` (264 bytes) | Best-practices gap |
| Peer structure (plain-terms lines, limits, key concepts, reproduce link, code excerpt) | `projects/13-model-serving/story.yaml` | Alignment target |
| Docs page mirrors the story | `docs/projects/15-dynamic-pricing-rl.md` | Must stay in sync with the story |
| Claim "a quarter of series at the 0.5 floor" is correct (25.3%) | `reports/experiment_log.json` step E2-2; recomputed from `data/calibration.json` | Keep; no change needed |

Opus's new figures (RL wins 35.1% of paired episodes; RL − B1 gap of −0.0013, −0.0105, −0.0174 by elasticity tercile, least to most sensitive) are **not in the repo**. They were computed in-session from committed files. Under truth-in-copy they cannot appear in copy until a committed script writes them to a committed report.

## Goals and non-goals

Goals:

- Project 15 reaches the 9.5 bar on Results and Best practices without changing any committed number or sealed result.
- Every new number in copy comes from a committed script and a committed JSON key.
- Remove the overclaims Opus named, with wording that matches the evidence.

Non-goals:

- **No new sealed read and no new policy evaluation.** `sealed_access.json` must not change. The test sets are consumed and cannot become tuning data.
- **No change to any committed RL metric value** or to the verdicts (P1 fail, P2 pass, P3 context only).
- **Project 01 stays at 8.8.** Its T cap needs a non-Moonshot hosted judge key, which only the owner can provide.
- **Project 08 stays at 8.8.** Its cap needs a second host (E11), which is not available.
- **The other twelve projects are not changed this round.** They need their own Opus review first (see Open questions).
- **No new paid or hosted calls.** Spend stays at $1.60 of the $5.00 cap.

## Constraints

- Repository conventions and gates: `AGENTS.md`; `docs/engineering/repo-conventions.md` (truth in copy, generated artifacts); `docs/engineering/code-quality-guidelines.md`.
- Metrics: any new key goes under the top-level `analysis` key. `_meta` stays provenance only. Restamp with `stamp_metrics_meta.py`.
- Generated artifacts: `story.yaml` feeds the static registry and the web build. Regenerate with `gen_static_registry.py` and `gen_story_short.py`, never by hand.
- No co-author trailers in any commit. No git mutations unless the owner asks; the owner commits.
- Do not touch `projects/08-inference-serving/data/bench_run_repeat.json` (gitignored, must stay untracked).

## Options

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| A. Copy fixes only, no new analysis | Fast; fixes the overclaims | Results stays at 9 (the gap is not explained) | If the owner wants the smallest change |
| B. Copy fixes plus a committed analysis script and `analysis` key, plus a model card and code excerpt | Closes Results and Best practices on the evidence | One script, one restamp, one docs sync | **Recommended** |
| C. B plus a new distribution figure of per-episode gaps | Strongest visual for the P1 verdict | Adds a figure, a caption and a chart gate | Stretch, only if B lands cleanly |

## Recommendation

Option B. It is the smallest change that closes the gap Opus named. It adds no new runs and changes no committed metric value. The paired-gap breakdown is computed from `test_episodes.json`, which is already committed. Option C is optional and is not required for the handoff to close.

**Grade hold, recommended:** set project 15 back to 9.0 in `phase-7-result.md` until the analysis is committed and Opus confirms Results at 9.5 or higher. The 9.3 was recorded on V 8→9 from the deploy browser check, and Opus's review puts Results at 9 and Best practices at 8.5. The recorded 9/10/9/9 is therefore ahead of the independent review. This is a grade decision for the owner, flagged here and not made.

## Acceptance criteria

- [ ] `reports/metrics.json` has a new `analysis` key containing: paired RL − B1 mean gap and 95% CI by elasticity tercile (computed from `test_episodes.json`); RL episode win share; the same by stock pressure `rho`. Written by a committed script, with the script path recorded in the key.
- [ ] Every committed RL number in `metrics.json` `test`, `stress`, `primary` is unchanged (value-for-value diff is empty outside `analysis` and `_meta`).
- [ ] `sealed_access.json` is byte-identical to its current version.
- [ ] `MODEL_CARD.md` has intended use (not for deployment), data, metrics by slice (from the new `analysis` key), and limits (one retained seed, simulator only, elasticity assumption).
- [ ] `story.yaml` has a code excerpt in the training section (the action mask or the paired bootstrap, taken from source, not invented).
- [ ] `story.yaml` results section states the gap by elasticity tercile, with the numbers from the new key.
- [ ] Copy fixes: "consistent across repeated checks" replaced; "proves safe behaviour" replaced with the zero-violation claim; "learned well" replaced with a concrete comparison; plain-language glosses for M5, MaskablePPO, action mask and comparator in the lead.
- [ ] Limits state that only seed 1 was retained, and that B1 also beat RL on validation.
- [ ] The conclusions section has a `## Results summary` heading, as ten of the thirteen peers do.
- [ ] `docs/projects/15-dynamic-pricing-rl.md` matches the story text for every changed claim.
- [ ] All gates in the verification section pass with exit 0.

## Rollback and failure behavior

- Failure modes: a new number that does not match the recomputed value; a metric changed by a restamp; a sealed file altered; a story/docs mismatch; a registry or web build failure.
- Observability: `git diff` on `metrics.json` outside `analysis` and `_meta` must be empty; `sealed_access.json` hash before and after.
- Rollback path: revert the single commit. The sealed log is append-only, so a rollback cannot restore a consumed read; it is never touched in this round.

## Decisions (owner, 2026-11-27)

- **Project 15 grade:** held at 9.0 until the analysis is committed and Opus confirms Results at 9.5 or higher. The 9.3 record is withdrawn for now.
- **Rubric mapping:** Language folds into Contents; Best practices folds into Technologies. Grade table keeps Contents, Results, Technologies, Visualizations.
- **Other twelve projects:** not in this round. An Opus per-project review against the 9.5 bar comes first, in its own design cycle.
- **Figure C (per-episode histogram):** deferred. Option B only.
