# Implementation handoff: execution plan for the RAG roadmap (project 01)

Date: 2026-11-22
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-22: "Approve local steps") for steps 0, 2, 3, 4, 5 and 6 (local, no hosted spend). Step 1 (judge labels) is approved from 2026-11-23 with Kimi as labeller, see Revision 3. The end-to-end run is not in this handoff; it needs its own.
Source design: `collaboration/designs/20261122-rag-execution-plan/01-design-brief.md`

## Objective

Produce a pinned retrieval baseline on dev_v1, a judge calibration set, and up to three retrieval changes measured on dev with a final check on final_v3. Record each step in `reports/experiment_log.json`. No hosted calls.

## Scope

### In scope

- Coverage check fix and a clean working tree (step 0).
- Judge calibration set, drafted by Sonnet, checked by the owner (step 1, after budget approval).
- Retrieval baseline and sweeps on dev_v1, local only (steps 2 to 4).
- Dev growth to 40 and 65 for any promising change (step 4).
- Final check on final_v3, once per candidate (step 5).
- Experiment log and a closing summary (step 6).

### Out of scope

- Any hosted model call (kimi-for-coding or otherwise).
- Edits to `src/rag_agent/` logic, prompts, or judge code. Sweeps change only config values through a new config file.
- Merges, pushes, branch deletion, or any change to project 02.
- Committing the 34 uncommitted working-tree changes that predate this plan.

## Affected surfaces

- `projects/01-rag-agent/configs/sweeps/` (new): one config per candidate.
- `projects/01-rag-agent/scripts/` (new): `measure_retrieval.py`, `build_judge_calibration_v2.py`.
- `projects/01-rag-agent/reports/retrieval_baseline/` and `reports/retrieval_sweeps/` (new).
- `projects/01-rag-agent/reports/judge_calibration_v2/` (new).
- `projects/01-rag-agent/reports/experiment_log.json` (new).
- `projects/01-rag-agent/data/judge_v2_claims.json` (new), with its sha256 manifest.
- `collaboration/reviews/20261122-rag-execution-plan/00-closeout.md` (new).

## Ordered implementation steps

### Step 0: prerequisites (no spend)

1. Confirm the branch: `git branch --show-current` must print `phase0-infra-2026-11-22`. Stop if not.
2. Fix the coverage run. The earlier run reported "No data was collected" for `libs`. Run `uv run pytest --cov` from `projects/01-rag-agent` and record the project coverage. The floor is 78.45%. Report the number verbatim, whether or not it passes.
3. Do not stage or commit the 34 uncommitted changes. Report the list with `git status --short` so the owner can decide.

### Step 1: judge calibration set (blocked until owner budget)

1. Build 150 claims from tuning-65 and dev_v1 gold chunks only. Never read final_v3 or sealed-120 claims for this step.
2. Write each claim as `{claim, chunk_id, chunk_text, kind}` with `kind` in {supported, unsupported}. Target 75 each.
3. Kimi (kimi-for-coding) labels every claim, per Revision 3: `supported` or `unsupported`, with a one-line reason. Save raw responses under `reports/judge_calibration_v2/raw/`.
4. The owner labels a random sample of 30 from the same set. Record agreement with Sonnet and the 95% Wilson interval.
5. Stop if Sonnet's agreement with the owner sample is below 85 per cent. Report the disagreements; do not relabel.
6. Commit `data/judge_v2_claims.json` with its sha256 manifest once the owner sample is recorded.

### Step 2: retrieval baseline on dev_v1 (local)

1. Pin the config: chunk 200, top_k 3, rerank on, MiniLM embeddings, the `retrieval_best` values in `params.yaml`. Note the README's rerank 5×k against top_k 3: record which value the code actually uses and say so.
2. Run `measure_retrieval.py --split dev_v1`. Record recall@5, MRR, and tokens per query. Save the config hash and commit.
3. Write `reports/retrieval_baseline/dev_v1.json`.

### Step 3: sweeps on dev_v1 (local)

Run one change at a time against the step 2 baseline:

1. Chunking: 200, 400, 800 with overlap 40. Then section-aware chunking if one of the sizes wins.
2. Embeddings: MiniLM against `bge-small-en-v1.5` and `e5-small-v2`, on the chunking that won.
3. Reranker: the current cross-encoder against one stronger open reranker, with the candidate count held fixed.

For each run, write `reports/retrieval_sweeps/<change>.json` and append one row to `reports/experiment_log.json`.

### Step 4: promote and grow

1. A change is promising if recall@5 on dev_v1 rises by at least 0.10 over the baseline.
2. For each promising change, grow dev to 40, then 65, and report the lift at each size. Keep the change only if the lift holds at 40.
3. Record kept or rejected, with the reason.

### Step 5: final check (once per candidate)

1. For each kept candidate, run `measure_retrieval.py --split final_v3` once. Do not rerun it with a different config.
2. Record the result in the log. If the final result is worse than the baseline on recall@5, mark the candidate rejected.

### Step 6: close-out

Write `collaboration/reviews/20261122-rag-execution-plan/00-closeout.md` with: the baseline, each change and its before and after numbers, the judge calibration result, anything rejected and why, and what needs owner decision next.

## Commands and gates

```bash
cd /Users/alejandro/work/portfolio/projects/01-rag-agent
uv run pytest --cov
uv run ruff check . && uv run ruff format --check . && uv run mypy .
cd ../..
uv run python scripts/check_docs.py
```

Run the project gates before every commit. Report the actual output verbatim.

## Generated artifacts

- `data/judge_v2_claims.json` and its manifest: from `build_judge_calibration_v2.py`.
- `reports/retrieval_baseline/dev_v1.json`, `reports/retrieval_sweeps/*.json`, `reports/experiment_log.json`: from `measure_retrieval.py`.

## Acceptance criteria

- [ ] Coverage measured and reported verbatim (step 0).
- [ ] Pinned baseline on dev_v1 with recall@5 and MRR (step 2).
- [ ] Up to three sweeps, each logged with before and after (step 3).
- [ ] Judge set of 150 with Sonnet and owner-sample agreement, if step 1 is unblocked.
- [ ] Final check run once per kept candidate, logged (step 5).
- [ ] Close-out written with each claim cited to a file.
- [ ] No hosted calls. Verify with the request-host log.

## Stop conditions

- Any request to a host other than `127.0.0.1` or `localhost`.
- Any read of final_v3 or sealed-120 question files before step 5.
- Sonnet's agreement with the owner sample below 85 per cent.
- Any write outside `data/`, `reports/`, `configs/sweeps/`, `scripts/`, or `collaboration/reviews/20261122-rag-execution-plan/`.
- Any failing gate that is not a known pre-existing failure. Do not weaken tests.

## Commit

Branch `phase0-infra-2026-11-22`. Commit only the files listed under affected surfaces, after the gates pass. No `Co-Authored-By` trailer for any model. Do not push. Do not merge. Do not touch project 02.

## Risks and open questions

- Resolved 2026-11-23: Kimi is the step 1 labeller (Revision 3). It is the same family as the executor, so the owner sample is the bias check.
- dev_v1 is 20 questions and comes from the tuning set that chose the current config. Dev lifts are not clean evidence; only final_v3 is unbiased.
- The coverage floor may still fail after step 0. If it does, report the number and stop; do not lower the floor.
- The 34 uncommitted changes may conflict with this work. Keep them out of every commit.

## Revision 1 (designer review of Kimi's plan, 2026-11-23)

Kimi's plan is accepted except for the following, which are binding:

1. **Reranker candidate:** `Qwen/Qwen3-Reranker-0.6B` is not loaded with `trust_remote_code=True`. Either pin the revision and review the repo code before any load, or drop this candidate and record the reason in the log.
2. **Gitignored outputs:** do not use `git add -f`. Gitignored outputs under `reports/` are written but not committed. Report which paths are ignored. Committing them needs an owner decision (a narrow `.gitignore` exception or an explicit list).
3. **Uncommitted redraft files:** report the 27 `reports/final_v3_drafts/redraft_*` files as uncommitted provenance for `golden_final_v3`. Do not stage them. The owner decides whether they go in a separate commit.
4. **Embedding substitution:** `qwen3-embedding:0.6b` replaces `e5-small-v2`. Record the substitution in `experiment_log.json` and the close-out.
5. **final_v3 reads:** the baseline on final_v3 in step 5 counts as one of the one-time final uses. The report says so. Each kept candidate is run once on final_v3 with no reruns.
6. **Scope:** no `.gitignore` or `pyproject.toml` edits. Coverage changes are invocation-level only.

## Revision 3 (owner decision, 2026-11-23): Kimi labels step 1

Steps 0 and 2–6 are already executed (commits `1663dd3`, `7e3246a`). This revision covers step 1 only, and replaces the Sonnet labeller in step 1 item 3.

1. **Labeller:** kimi-for-coding, a hosted call, used for step 1 labelling calls only. No other hosted call is permitted.
2. **Spend:** counted against the $3.00 kimi-for-coding cap in the design brief, which is shared with the end-to-end run. Stop and report if estimated spend reaches $3.00. Any split between step 1 and the end-to-end run is the owner's to set; none is set here.
3. **Endpoint:** name the Kimi API host before the first call and record it in the log. This is the one permitted non-localhost host, for step 1 only.
4. **Spend record:** each call logs model, token counts and estimated cost to `reports/judge_calibration_v2/raw/` and to `reports/experiment_log.json`. Report the running total at the end of step 1.
5. **Owner sample:** labelled by the owner by hand. No model labels it. The 85% agreement threshold in step 1 item 5 is unchanged.
6. **Stop conditions added:** estimated spend at $3.00; any hosted call outside the named Kimi host; any labelling of final_v3 or sealed-120 claims.
7. **Revision 1 still applies.**

## Revision 4 (designer, 2026-11-23): redo the unsupported claims

The step 1 run under Revision 3 produced 150 labelled claims. Its 75 unsupported claims are too easy: about 40 pair a claim with a passage on an unrelated topic, and the labeller matched construction truth 150/150, so the set cannot calibrate the judge. Revision 4 replaces the unsupported half. The 75 supported claims are kept as they are.

1. **Archive, don't delete:** move `data/judge_v2_claims.json`, its manifest, and `reports/judge_calibration_v2/raw/` to `reports/judge_calibration_v2/superseded_v2a/` before writing anything new. Keep the `owner_sample.json` from v2a there too.
2. **Negative construction:** for each kept supported claim's chunk, draft one unsupported claim with a local model (`qwen3.6:35b-a3b-q4_K_M` via `127.0.0.1` only). The claim must be on the same subject as the chunk. It must change exactly one detail (a date, a quantity, a relation, a comparison, or an attribute) so that it is plausible but not stated or implied by the passage. Target 75 negatives.
3. **Negative checks, all in code:**
   - the changed term is absent from the chunk (case-insensitive) and is at least 4 characters or a number;
   - the claim shares at least 3 content words with the chunk (topical overlap);
   - the claim is not a duplicate of another claim, and no two claims share a token sequence of length 8 or more;
   - a claim that fails a check is redrafted, up to 3 attempts, then dropped and reported.
   Report the count dropped and the overlap distribution.
4. **Labelling:** the labeller is kimi-for-coding, as in Revision 3, using the same prompt, blind to construction. Reuse the spend ledger and the $3.00 hard stop. Log the call count and cost again. Local drafting costs nothing.
5. **Owner sample, redrawn:** draw 30 from the new set (seed 44) and write `owner_sample.json` with `index`, `claim`, `chunk_id` **and `chunk_text`**, unlabelled. The owner sample must include the evidence.
6. **Agreement stays unset:** do not compute agreement until the owner's labels are in. The 85% threshold is unchanged.
7. **Stop conditions added:** any negative drafted without a local model; any non-localhost host other than the Kimi host named in Revision 3; any step-1 spend past $3.00.
8. **Revision 1 and 3 still apply.** Nothing is staged or committed. Gates as before.

## Revision 5 (designer, 2026-11-23): fix negative drafting 8-gram check, caching, and retry non-determinism

Revision 4's execution hit an impasse in `build_judge_calibration_v3.py`:
- Candidate negatives were checked against a global 8-gram set that included their *own* source claim (and 6 duplicate supported claims in `superseded_v2a/judge_v2_claims.json`). Because one-detail negative construction preserves the rest of the sentence, any source sentence longer than 8 words collided with itself.
- `changed_term_ok` used raw substring matching (`term.lower() in chunk_text.lower()`), falsely rejecting words like `"complete"` when `"incomplete"` appeared in the chunk, and `_NUMBER_FULL` rejected numbers with units/symbols like `"25%"`.
- Retry attempts 2 and 3 used identical prompts with `temperature: 0` and static `SEED`, producing identical outputs.

Apply these 5 exact fixes to `projects/01-rag-agent/scripts/build_judge_calibration_v3.py`:

1. **Reuse cached `attempt1` drafts:** In `generate(prompt, slot, attempt, temperature=0.0, seed=SEED)`, compute `prompt_sha = hashlib.sha256(prompt.encode()).hexdigest()`. If `(DRAFTS / f"{slot}_attempt{attempt}.json")` already exists and its JSON `"prompt_sha256"` equals `prompt_sha` and `"response"` is non-empty, append `"localhost"` to `HOSTS` and return the cached `"response"` immediately without calling Ollama. (This reuses the 45+ already-generated `attempt1` drafts in <1 second.)
2. **8-gram scope by claim text (excluding self):** For item `i` with source claim `item["claim"]`, define `src_grams = token8(item["claim"])`. Build `other_supported_grams` from all `supported_items` whose `claim != item["claim"]`. Reject on 8-gram collision only when `(token8(negative) - src_grams) & (other_supported_grams | accepted_neg_grams)` is non-empty, and when accepted add `(token8(negative) - src_grams)` to `accepted_neg_grams`.
3. **Word-boundary & digit-aware `changed_term_ok`:**
   - Check presence in `chunk_text` with word boundaries when `term` starts/ends with alphanumeric characters (`re.search(rf"\b{re.escape(term.lower())}\b", chunk_text.lower())`), so `"complete"` does not match `"incomplete"`.
   - Allow short numeric terms containing any digit (`len(term) < 4 and not re.search(r"\d", term)`) so `"25%"` or `"4°C"` pass.
4. **Retry variation and failure feedback:** On attempts 2 and 3, append `\n\nNote: previous attempt failed check ({last_reason}). Change a DIFFERENT detail (date, number, comparison, or attribute) using a word/number that does NOT appear anywhere in the passage.` to the prompt, and call `generate` with `temperature=round(0.25 * (attempt - 1), 2)` and `seed=SEED + attempt`.
5. **Execution order:** Interrupt any stuck Revision 4 run of `build_judge_calibration_v3.py`, apply the 5 fixes above, run `HF_HUB_OFFLINE=1 uv run python scripts/build_judge_calibration_v3.py`, then run `uv run python scripts/label_judge_calibration_v2.py` (`kimi-for-coding` within the $3.00 hard cap) to produce `data/judge_v2_claims.json`, `data/judge_v2_claims.sha256.json`, and unlabelled `reports/judge_calibration_v2/owner_sample.json` (30 items, seed 44, including `chunk_text`). Run project 01 gates (`ruff`, `mypy`, `pytest --cov`) and report results.
