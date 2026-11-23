# Review response: RAG execution plan (project 01) — steps 0, 2–6 and Revision 4

Date: 2026-11-23
Reviewer: Claude Code
Implementation: commits `1663dd3`, `7e3246a` on `phase0-infra-2026-11-22`, plus uncommitted `build_judge_calibration_v3.py`
Status: changes requested

## Verdict

Steps 0, 2, 3, 4, 5, and 6 satisfy the handoff and are cleanly executed and reported in `collaboration/reviews/20261122-rag-execution-plan/00-closeout.md`. The baseline on `dev_v1` is pinned, the sweeps cleanly proved zero lift for all challengers (confirming the incumbent configuration as champion), and the unbiased `final_v3` baseline was established (Recall@5: 0.9239, MRR@5: 0.8793).

However, **Step 1 (Judge calibration under Revision 4)** is blocked by a critical constraint bug in `build_judge_calibration_v3.py`: the 8-gram duplicate check compares generated negative claims against a global set that includes each negative's *own* source claim. Because the negative generation prompt explicitly instructs changing only one detail while keeping the rest identical, nearly every sentence longer than 8 tokens shares an 8-token run with its source claim. Coupled with deterministic generation (`temperature: 0`), all retry attempts fail identically, dropping valid negatives.

## Required changes

| Severity | Finding | Evidence | Required resolution |
|---|---|---|---|
| blocker | `build_judge_calibration_v3.py` checks 8-grams against the negative's *own* source claim (plus 6 duplicate supported claims in `superseded_v2a`) | `negatives` generation drops almost all drafts; e.g., `neg_000`, `neg_001`, `neg_002` fail with `shares an 8-token sequence with another claim` despite only modifying a single fact | Compute `src_grams = token8(item["claim"])` and check `(token8(negative) - src_grams) & (other_supported_grams | accepted_neg_grams)` where `other_supported_grams` excludes any supported item with `claim == item["claim"]`. |
| major | Substring false-positive and strict regex in `changed_term_ok` | `"complete"` rejected because `"incomplete"` is in the chunk (`neg_002`); `"25%"` rejected because `_NUMBER_FULL` forbids `%` (`neg_011`) | Use word-boundary matching (`\b...\b`) when `term` is alphanumeric-bounded, and accept `<4`-char terms containing any digit (`re.search(r"\d", term)`). |
| major | No draft caching + deterministic retries on validation failure | `generate()` re-runs Ollama even when `attempt1` is cached on disk, and hardcodes `{"temperature": 0, "seed": SEED}` with the same prompt on retries 2–3 | Cache-hit `(DRAFTS / f"{slot}_attempt{attempt}.json")` when `prompt_sha256` matches (instant recovery of 45+ `attempt1` drafts), and on `attempt > 1` append the failure reason to the prompt with `temperature = 0.25 * (attempt - 1)` and `seed = SEED + attempt`. |

## Suggestions

| Suggestion | Reason | Owner decision needed |
|---|---|---|
| Keep uncommitted `reports/final_v3_drafts/redraft_*` in a dedicated provenance commit | 27 draft files represent verifiable history of `golden_final_v3` | Yes: commit to `phase0-infra-2026-11-22` or drop from tree |
| Add narrow `.gitignore` exception for `reports/experiment_log.json` | Experiment log tracks historical sweeps and lift decisions required by the RAG roadmap | Yes: allow committing `reports/experiment_log.json` |
| Resolve Project 02 working-tree diff | `reports_m5_full/evaluation_metadata.json` and `metrics.json` were updated for 10 origins (~1.3M sec runtime) | Yes: leave unstaged or commit to a separate branch |

## Verification checked

- [x] Scope matches the handoff for steps 0, 2–6
- [x] Baseline and sweep reports conform to local execution rule (`request_hosts: []` or `['127.0.0.1']`)
- [x] Touched gates are green (`check_docs.py`, `check_short_copy.py`, `check_demo_contract.py`, `lint_story_language.py`, `gen_static_registry.py`, `pytest` on project 01)
- [ ] Step 1 judge calibration dataset produced and verified (blocked on Revision 5 resolution)

## Closure

- Required findings resolved: Pending resolution of blocker/major in Revision 5
- Remaining risks: Step 1 spend on `kimi-for-coding` when labelling resumes (must stay within $3.00 cap)
- Recommended next step: Owner approves Revision 5 (amendment to `build_judge_calibration_v3.py`), Kimi executes the negative generation and labelling, and the owner reviews the 30-claim sample to validate judge agreement before proceeding to the end-to-end evaluation pass.
