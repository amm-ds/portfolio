# Implementation handoff: TabPFN-2 challenger for project 12 (bike demand)

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code (owner runs it)
Owner: amm-ds
Status: dropped (owner, 2026-11-19). Originally APPROVED by owner on 2026-11-19 for Kimi execution; stopped at step 3 when the weights required a Prior Labs token/licence acceptance, and the owner then dropped the challenger. Licence reviewed: the Prior Labs License v1.1 has no commercial-use restriction and requires attribution (see below).

## Objective

Run TabPFN-2 locally on the bike-sharing data as a challenger to the served MLP and LightGBM, under a documented subsample, and record the result as a validation comparison. No hosted calls.

## Licence conditions (must be met in the same change)

From the Prior Labs License v1.1 (Section 10), as reported from the Hugging Face LICENSE files. Kimi must confirm the wording against `https://huggingface.co/Prior-Labs/TabPFN-v2-clf/blob/main/LICENSE.txt` before writing the attribution text:
- Display "Built with PriorLabs-TabPFN" prominently on the project's page and README.
- Ship a copy of the licence with the project (`projects/12-tabular-ml-lifecycle/LICENSE-TABPFN.txt`, copied from the Hugging Face file, not retyped).
- Do not name any trained or fine-tuned model distributed from these weights with a name that does not begin with "TabPFN" (not expected here; state it in the card).

## Scope limit

Document the sample cap: TabPFN-2 is evaluated in the source paper up to 10,000 samples. The bike training split has 14,523 rows, so the run uses a seeded subsample of the training split (10,000 rows, seed 42, same split logic as the served models). The test window stays frozen and unchanged. The card states the subsample size next to the result.

## Steps

1. Check PyPI for the current `tabpfn` release that bundles TabPFN-2 weights and record the exact version. Do not assume a version. Stop if no TabPFN-2-compatible release exists.
2. Add the pinned dependency to `projects/12-tabular-ml-lifecycle/pyproject.toml` and run `uv lock`. Do not hand-edit `uv.lock`.
3. Confirm weights load offline with no token. If a token or licence acceptance is requested, stop and write `OPEN_QUESTIONS.md`.
4. Add a challenger run script or CLI command under `projects/12-tabular-ml-lifecycle/src/`, reading only the train and validation partitions, writing results to `reports/tabpfn2_challenger.json` (new file).
5. Compare with the served MLP and LightGBM on the validation split with the paired bootstrap already used for the validation tie. Report MAE and the interval.
6. Update the project 12 README, story and short copy only to state the result. Do not change the served model, the tie claim or any existing headline number. If the challenger beats the served model, stop and write `OPEN_QUESTIONS.md`: the served-model choice needs an owner decision.
7. Regenerate short copy with `scripts/gen_story_short.py`. Do not hand-edit generated files.

## Gates

- `uv run pytest -q projects/12-tabular-ml-lifecycle`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps`
- `uv run python scripts/lint_story_language.py`, `scripts/check_docs.py`, `scripts/check_short_copy.py --check`, `scripts/gen_story_short.py --check`, `scripts/check_headline_numbers.py`
- Web gates only if `storyShort.ts` changes: `npm test`, `npm run lint`, `npm run build`.

Do not claim a gate passed unless you ran it.

## Stop conditions

- A headline number changes.
- The weights need a token or a licence acceptance.
- The challenger beats the served model.
- Any change would touch `.env`, permissions or config, or require a git mutation.

## Acceptance

- Attribution line and licence copy present in the project.
- Sample cap stated beside the result.
- `reports/tabpfn2_challenger.json` committed as a new file only; no existing report overwritten.
- Gate results as actually run, listed in the report.

## Report

Write `collaboration/reviews/20261119-tabpfn2-report/00-report.md`: the PyPI version used, the licence text checked, files changed, commands run, the validation comparison with its interval, and any open question.
