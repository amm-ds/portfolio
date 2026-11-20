# Verifier cascade DEV-only calibration report

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-verifier-cascade-dev/03-implementation-handoff.md`
(approved: offline DEV-only calibration, $0 hosted; nothing else)
Branch: `verifier-cascade-2026-11-20` from `verifier-challenger-2026-11-20`
(head `c574680`). No merge, no deploy, no copy or headline changes, zero
hosted calls.

## Verdict

**No qualifying band.** Across all 4,095 grid bands on cross-validated DEV, no
`(t_lo, t_hi)` pair meets FA ≤ 0.10 AND FR ≤ 0.10. Per the frozen rule, TEST
was **not read** (Step 5 vacuous — no commit produced for it). The cascade
fails on DEV before touching TEST; the project keeps the Phase 1 challenger
result as the verifier record.

## Commits and push

- `3d47d8b` — `docs(01): verifier cascade - frozen DEV-only rule and folds, before scoring`
- `1108f46` — `feat(01): verifier cascade - local judge verdicts cached for 194 claims`
- `d973010` — `feat(01): verifier cascade harness and tests`
- `6137f49` — `feat(01): verifier cascade - DEV CV selection and final fit`
- Pushed: `git push -u origin verifier-cascade-2026-11-20` ✓ (after Step 1;
  remaining commits pushed at the end of this report)

## Frozen artifacts (sha256)

- Rule: `reports/verifier_cascade_dev/rule.md`
  sha256 `081c45c8b57fcf370f0794fb76961272504dd4621a53bef5207ce0a0bda39630`
- Folds: `reports/verifier_cascade_dev/folds.json`
  sha256 `76c76fc4a5a12fe4723c45604eabd117f5e9d4d5423ca9f6736f7287ab9e5d47`
- Predictions (DEV decisions): `reports/verifier_cascade_dev/predictions.jsonl`
  sha256 `76a94287d83c4e08790b931e6b28206da5a5a1ad82e83528403ef86581d76226`
- Local verdicts cache: `reports/verifier_cascade_dev/local_verdicts.jsonl`
  sha256 `d03e6251daccb069411ce0ee5e7523d179dbba6bd25d4a3ea1e9d3e5dee52d3f`
- Ollama digest: `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`
  (qwen2.5:3b, 1.93 GB, verified via `/api/tags` before and during the run)

## Step 2 — local judge cache

194/194 claims judged in 309.19 s, **0 unparseable verdicts**, all requests
to `http://localhost:11434` (forced-local Settings; the one HF-free, hosted-free
run). Reconciliation against the committed local aggregate FA 0.4433
(all-claims denominator): this run gives FA 23/194 = **0.1186**
(FA strict 23/97 = 0.2371; FR 12/97 = 0.1237). The difference is expected and
stated, not hidden: the committed aggregate used `calibrate_judge.py`'s strict
entailment prompt; this cached run uses judge.py's 0–1 rubric prompt with a
0.5 cut (frozen rule item 7). Same model, different operating point — the
rubric judge is far more lenient on unsupported claims and somewhat stricter
on supported ones.

## Step 4 — CV selection landscape

Grid: **4,095 bands** over 91 unique DEV MiniCheck scores; 5-fold CV on DEV
(96 claims), deferred claims resolved by the cached local verdicts. Summary:

| Band (t_lo, t_hi) | CV FA | CV FR | Deferred | Note |
|---|---|---|---|---|
| [0.9799, 0.9814] | 0.0000 (0/48) | 0.9167 (44/48) | 0.0% | lowest FA — rejects nearly everything supported |
| [0.0629, 0.9410] | 0.1458 (7/48) | 0.0000 (0/48) | 2.1% | lowest FR — accepts too much unsupported |
| [0.0839, 0.9410] | 0.1458 (7/48) | 0.0000 (0/48) | 0.0% | lowest deferred — no middle band used |
| [0.9599, 0.9696] | 0.0833 (4/48) | 0.2292 (11/48) | 19.8% | best FA within cap — FR far over |
| [0.0839, 0.9696] | 0.1042 (5/48) | 0.0833 (4/48) | 29.2% | closest to both caps — FA just over 0.10 |

Qualifying bands: **0 of 4,095**. Full per-band table:
`reports/verifier_cascade_dev/cv_results.jsonl`.

Reading: the overlap between the MiniCheck score distributions plus the
middle-band judge's own error rate (its verdicts flip enough claims near both
cut points) means every band trades one criterion against the other; the
closest misses sit within ~1 point of one cap only by deferring ~20–30% of
claims to a judge that is itself too noisy to hold the other cap. This is the
same stricter-verifier trade-off measured in R8 and the Phase 1 challenger
run, now measured jointly over the whole threshold grid.

## Step 5 — TEST

**Not read.** No band qualified, so the frozen rule forbids the TEST reading.
No Step 5 commit exists.

## Gates (actual output)

- `uv run pytest -q projects/01-rag-agent` → **197 tests passed, 0 failed**
  (186 pre-existing + 11 new); exit 1 solely from the pre-existing libs
  coverage gate: `ERROR: Coverage failure: total of 78 is less than
  fail-under=80` / `FAIL Required test coverage of 80.0 not reached. Total
  coverage: 78.19%`. Known before this work (subset effect: `--cov=libs`
  needs other projects' tests to reach 80%; identical without the new tests).
  Suite result and coverage reported separately per the handoff.
- `uv run ruff check projects/01-rag-agent` → `All checks passed!`
- `uv run ruff format --check` on the 3 new files → `3 files already formatted`
- `uv run mypy projects/01-rag-agent/src projects/01-rag-agent/scripts` →
  `Success: no issues found in 34 source files`
- `uv run python scripts/check_headline_numbers.py` →
  `11 claims checked, 0 finding(s)` / `OK`
- `uv run python scripts/check_docs.py` → `check-docs: OK`

## No-hosted-calls statement

Zero hosted calls. The only network traffic in this pass was to
`http://localhost:11434` (Ollama; verified in the run log, one request per
claim) — the model was forced-local by construction
(`Settings(llm_base_url=None, llm_api_key=None)`, env kwargs beat the `.env`
file). Hosted spend: **$0**.

## Open questions

- The owner decision this informs: with the single-threshold challenger
  (Phase 1: FA 0.041 / FR 0.143 on TEST, gate FAIL on FR) and the cascade
  (no DEV-qualifying band), the verifier options tried so far all hit the
  same FA/FR trade-off wall at this label set and judge quality. A different
  middle-band judge (e.g. a stronger local model) or a hand-labeled refresh
  of the 10 `manual_review` rows are new-decision territory, not this
  handoff's scope.
- The 0.08 FR sensitivity the design brief flagged was not run: with zero
  qualifying bands at 0.10, tightening would not change the outcome.
