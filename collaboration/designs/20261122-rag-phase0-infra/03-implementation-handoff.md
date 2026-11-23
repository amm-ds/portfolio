# Implementation handoff: Phase 0 (clean splits) and checkpoint/spend infrastructure (revision 2)

Date: 2026-11-22
Designer: Claude Code
Executor: Kimi Code
Status: approved for revision 2 (owner, 2026-11-22: new untouched final test set; $3 maximum hosted cap on kimi-for-coding; plan approved). Revision 2 incorporates a Sonnet review (agreement with changes) and the owner's constraints.
Sources: `collaboration/designs/20261122-rag-roadmap/01-design-brief.md`.

## Objective

1. Build a new untouched **final test set** `final_v3` (120 questions, stratified 68 single-hop / 24 multi-hop / 28 unanswerable), with no overlap with any existing set.
2. Build a clean **dev split** `dev_v1` (20 questions) with a leakage report.
3. Make the run infrastructure safe for paid work (checkpoints, persistent spend, Kimi pricing check, sealed guard, request-host logging). No paid run in this handoff.

## Spend and model rules (revised)

- **Drafting is local.** Question drafting and the answerability check use the local open model `qwen3.6:35b-a3b-q4_K_M` on Ollama (`127.0.0.1:11434`). This costs nothing from the $3 cap and keeps the test set from being written by the same model that answers it (self-preference).
- **Hosted calls in this handoff: none.** Any hosted call is a stop condition.
- **Model roles are separate.** Drafting and the answerability check: local `qwen3.6:35b-a3b-q4_K_M`. Answering and judging in later runs: `kimi-for-coding` (hosted, capped, only in those later runs). The pipeline's default open-model configuration is unchanged; hosted Kimi is used only for the capped runs named in the roadmap. If a later run uses Qwen as the answering model, self-preference against the drafting model returns and must be disclosed.
- **No final_v3 run** of any kind is allowed before Stage 2 (owner acceptance and sha manifest).
- **The $3 cap** (kimi-for-coding only) applies to later answering and judging runs. It is not spent here. Its enforcement and price check are in Part C.
- **Claude models** (Sonnet, Opus) are not used in this handoff. Labelling with them needs a separate owner budget.
- **Local request guard:** all model requests go to `127.0.0.1` or `localhost`. Log each request host; stop on any other host.

## Part A: final_v3

Script: `projects/01-rag-agent/scripts/build_final_v3.py`.

1. **Source.** Corpus `projects/01-rag-agent/data/raw/corpus.jsonl` (593 articles). Chunk with the production chunker at 200 tokens. Record the chunk ids used.

2. **Read-restriction (enforced).** Drafting reads only the corpus file and its chunks. The script must not open `src/rag_agent/eval_questions.json`, `data/golden_*.json`, or any stress file. It writes an access log (`reports/final_v3_file_access.json`) listing every file opened; the log must show no question file.

3. **Single-hop (68).** For each drafted question: a natural question answerable from one article. Prompt: fixed text, stored in the script with its sha256. Output JSON: `question`, `answer`, `gold_chunk_ids`, `relevant_titles`. Keep the answer supported by a gold chunk.

4. **Multi-hop (24).** Take two named articles in the same topic that share an entity. A question that needs both. `gold_chunk_ids` must cover both articles. `relevant_titles` lists both.

5. **Unanswerable (28).** Protocol, all steps required:
   - Draft a plausible question on a topic adjacent to the corpus but not covered by it.
   - Fill `absent_terms`: the key terms the question needs.
   - Verify by corpus-wide search (case-insensitive substring over all 593 articles) that no chunk contains the `absent_terms`.
   - Verify the question's topic is not an article title in the corpus.
   - Keep only drafts that pass all checks; redraft otherwise.

6. **Answerability check (local model, second pass).** For each answerable question, the local model is asked whether the question is answerable from its gold chunks only. Record the answer and agreement. Report how often the question is answerable from non-gold retrieved chunks alone; do not drop on that figure.

7. **Overlap validator.** Against all of: `src/rag_agent/eval_questions.json` (tuning-65), `data/golden_heldout.json` (heldout-55), `data/golden_sealed_v2.json` (sealed-120), `data/golden_sealed_v2_58.json`, `data/golden_stress_*.json`.
   - Exact duplicate question text: zero.
   - Token Jaccard: below 0.4.
   - Embedding cosine (local MiniLM, `sentence-transformers/all-MiniLM-L6-v2`): below 0.85 for every pair. Record the threshold in the report.
   - Title overlap with sealed-120: report both the count of unique titles and the count of questions whose gold title appears in sealed-120. Target: at most 5% of unique titles. Report the figure.
   - Title overlap with tuning and heldout: report, do not gate.
   - Failing drafts are redrafted from different source articles. If a check still fails after 3 redraft attempts for one slot, stop and report that slot.

8. **Seed and temperature.** Set the seed if the local server supports it; otherwise temperature 0. Save every raw model response to `reports/final_v3_drafts/` so the drafts can be reproduced.

9. **Owner sample.** Write `reports/final_v3_review_sample.md` with a stratified sample of 30: 18 single-hop, 6 multi-hop, 6 unanswerable. Each item shows the question, gold chunks or absent terms, and the check results. Acceptance rule for the owner: at least 90% accepted (27 of 30). Reasons for rejection are recorded per item. On failure, the failed items and the category are redrafted, and a fresh sample of 30 from the new drafts is reviewed.

10. **Outputs.** `data/golden_final_v3.json` (120, original order, with fields `question`, `category`, `expected_behavior`, `relevant_titles`, `absent_terms`, `gold_chunk_ids`), `data/golden_final_v3.sha256.json`, `data/golden_final_v3.overlap.json`. The sha manifest is written only after the owner accepts the sample.

## Part B: dev_v1

1. Seeded pick of 20 ids from `src/rag_agent/eval_questions.json`: 12 single-hop, 4 multi-hop, 4 unanswerable, file order.
2. `data/dev_v1.sha256.json`: selected ids, source file sha256, counts.
3. Leakage report: dev_v1 vs sealed-120, final_v3, heldout-55. Zero exact duplicates.
4. Report must state: 20 questions is too few for F1 decisions; retrieval recall@5 and MRR are the decision metrics until dev reaches 65.
5. Report must state: dev_v1 is drawn from the tuning set, which was used to choose chunk size and retrieval config (`params.yaml` `retrieval_best`). Dev results are not clean for those choices. Only final_v3 gives an unbiased number.

## Part C: infrastructure (no paid run)

Changes limited to `src/rag_agent/runner.py` (new), `evaluate.py`, `metering.py`, `libs/portfolio-core/src/portfolio_core/llm_budget.py`, tests, and the gitignore exceptions.

1. **Per-question checkpoints.** `reports/runs/<run_id>/rows.jsonl`, appended and flushed per question. `manifest.json` records config hash, commit, dirty flag, split name, set sha256, index id, judge model, judge prompt hash. Resume skips question hashes already present when the manifest hash matches; refuse on mismatch.
2. **Persistent spend.** Store cumulative USD in the manifest; seed the ledger on resume (`get_ledger(seed_usd=...)`; default None keeps today's behaviour).
3. **Kimi price (revised).** Record the price for kimi-for-coding with its source. If no published per-token price exists for kimi-for-coding (the code notes `usage.cost` is None and uses a labelled reference), then:
   - record it as "unpublished; estimated at the kimi-k2.8-preview reference, $1.00 in / $4.00 out per Mtok";
   - the $3 cap then counts as estimated spend: soft stop at $2.00 estimated, hard stop at $3.00 estimated;
   - do not change `model_rate_card` silently; report the mapping.
4. **Sealed guard.** Verify the sha256 of any question file against its manifest before a run reads it; refuse on mismatch. The metrics writer (`evaluate.py`) writes `detail.heldout` only for the sealed-120 set. Dev and final runs write `detail.<split-name>` under `--reports-dir`, never the shared `reports/metrics.json`.
5. **Request hosts.** Log each request host per row, via an `httpx` log handler. Local-only steps run with `ALLOW_MODEL_REQUESTS=false`.
6. **File-write guard.** Runs may write only under `data/` (the new files) and `reports/`. Any other write is a stop.
7. **Tests** (`tests/test_runner.py`, plus a portfolio-core ledger seed test): resume after abort (no duplicate or lost rows); config-mismatch refusal; spend seeded from manifest; sha mismatch refusal; no `detail.heldout` write from a dev run; kimi rate resolution. Project 01 coverage ≥ 78.45%.

## Commands

```bash
cd /Users/alejandro/work/portfolio/projects/01-rag-agent
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy .
cd ../..
uv run python scripts/check_docs.py
```

Report the actual output verbatim. Run these before any commit.

## Acceptance

Split into three stages so B and C do not wait on the owner.

**Stage 1 (drafted):**
- [ ] `final_v3` drafted: 120 questions, stratified 68/24/28, gold ids present, unanswerable protocol completed.
- [ ] Overlap report: zero exact duplicates, Jaccard below 0.4, cosine below 0.85, title overlap figures reported.
- [ ] File-access log shows no question file was read during drafting.
- [ ] Owner review sample written (`reports/final_v3_review_sample.md`).
- [ ] Zero hosted calls.

**Stage 2 (frozen):** after the owner accepts the sample (at least 27 of 30):
- [ ] `golden_final_v3.json`, its sha manifest, and the overlap report are committed.

**Stage 3 (dev and infrastructure):** does not wait for the owner:
- [ ] `dev_v1` frozen with manifest and leakage report.
- [ ] Part C implemented and tests pass; coverage ≥ 78.45%.
- [ ] Kimi price recorded with its source or the estimated-reference rule applied.
- [ ] `check_docs.py` passes.

## Stop conditions

- Any hosted call or request to a host other than `127.0.0.1` or `localhost`.
- Any sealed or manifest sha mismatch, at startup or during a run.
- Any question file read during drafting, or any write outside `data/` and `reports/`.
- A slot that fails the overlap checks after 3 redraft attempts: stop and report that slot.
- Test failure after Part C: stop and report; do not weaken tests.

## Commit

Branch `phase0-infra-2026-11-22` from `main`. Commit only this handoff's files, after the commands pass. No `Co-Authored-By` trailer for any model. Do not push. Do not merge. Do not touch project 02 files.

## Required disclosure in the report

- The final F1 report must state: drafting and the local answerability check used `qwen3.6:35b-a3b-q4_K_M`; answering and judging use `kimi-for-coding` (or the named open model); the same-model answerability check is a known mild self-agreement bias, mitigated by the owner sample.

## Open decisions (owner, not blocking Stage 3)

- Whether the final set should be drafted by the local model (as here) or by Kimi (uses cap; higher draft quality, possible self-preference).
