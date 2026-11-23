# Implementation handoff: Phase E — Pipeline Bug Fixes, `dev_v1` E2E Gate, and Checkpointed `final_v3` 120-Question Evaluation (project 01)

Date: 2026-11-23
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution
Branch: `phase0-infra-2026-11-22`
Source design:
- `collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/01-design-brief.md`
- `collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/02-architecture-proposal.md`

## Objective

1. **Step 1 (Pipeline Bug Fixes & Unit Tests — Local, $0):** Fix the 3 end-to-end evaluation bugs identified in `src/rag_agent/evaluate.py` (line 740 truncated 240-char `c.excerpt` judge context), `src/rag_agent/verify.py` (`s.split()` punctuation attachment in `check_claim_spans`), and `src/rag_agent/agent.py` (Rule 5 bounded search calls on absent topics), and add unit tests in `tests/test_verify.py` and `tests/test_heldout.py`.
2. **Step 2 (`dev_v1` End-to-End Verification Gate — 20 Questions, `kimi-for-coding`):** Build `scripts/run_e2e_eval.py` (supporting `--split dev_v1` and `--split final_v3`) and run `dev_v1` (20 questions from `data/dev_v1.sha256.json`) writing `reports/e2e_dev_v1/metrics.json` and `reports/e2e_dev_v1/question_traces.json`. Verify per-question F1 $\ge 0.85$ and `budget_terminated == 0`.
3. **Step 3 (`final_v3` Checkpointed 120-Question End-to-End Evaluation):** Once `dev_v1` passes the gate, run the 120-question `data/golden_final_v3.json` evaluation via `uv run python -m rag_agent.cli evaluate --heldout --heldout-file data/golden_final_v3.json --reports-dir reports/final_v3_e2e` (and compute the per-question F1 / precision / recall / Wilson 95% CI summary via `scripts/run_e2e_eval.py --summarize reports/final_v3_e2e`), with soft stop `$2.50` and hard stop `$2.80` (keeping total Step 1 `$0.1994` + Phase E spend $\le \$3.00$).
4. **Step 4 (Gates & Close-out Report):** Run all project 01 gates (`pytest --cov`, `ruff`, `mypy`) and repo `check_docs.py`, log all runs in `reports/experiment_log.json`, and write `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md`. Do not commit; Claude will review, validate, and commit.

## Affected surfaces

- `projects/01-rag-agent/src/rag_agent/evaluate.py`
- `projects/01-rag-agent/src/rag_agent/verify.py`
- `projects/01-rag-agent/src/rag_agent/agent.py`
- `projects/01-rag-agent/tests/test_verify.py`
- `projects/01-rag-agent/tests/test_heldout.py`
- `projects/01-rag-agent/scripts/run_e2e_eval.py` (new)
- `projects/01-rag-agent/reports/e2e_dev_v1/` (new)
- `projects/01-rag-agent/reports/final_v3_e2e/` (new)
- `projects/01-rag-agent/reports/runs/` (checkpoint rows)
- `projects/01-rag-agent/reports/experiment_log.json`
- `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md` (new)

## Ordered implementation steps

### Step 1: Fix the 3 E2E Pipeline Bugs & Add Unit Tests (Local, $0)

1. In `projects/01-rag-agent/src/rag_agent/evaluate.py` (`run_rag_eval`, around lines 737–755):
   - Add a helper `_judge_context(evidence: list[Citation], cited: list[Citation], retriever: Retriever) -> str` that iterates over `[*evidence, *cited]`, deduplicating by `chunk_id`, and collects `chunk.text` when `retriever.get_chunk(c.chunk_id)` is not `None` (falling back to `c.excerpt` when `get_chunk` returns `None`).
   - Replace `context = "\n".join(c.excerpt for c in evidence)` with `context = _judge_context(evidence, output.citations, retriever)`.
   - Ensure `retrieved_relevant = retrieved_relevant or cited_relevant` when building `QuestionTrace` after `output` is produced (if the agent retrieved and cited a relevant article via `search_documents`, retrieval succeeded).
2. In `projects/01-rag-agent/src/rag_agent/verify.py` (`check_claim_spans`, lines 257–276):
   - Precompute `span_token_sets = [set(re.findall(r"[a-z0-9]+", s)) for s in span_texts]`.
   - In the number entity check (line ~262), check `any(w in span_tokens for w in others)` against the corresponding `span_tokens = span_token_sets[idx]`.
   - In the date/temporal token check (line ~266), check `any(token in span_tokens for span_tokens in span_token_sets)`.
   - In the negation check (line ~271), compute `span_words: set[str] = set().union(*span_token_sets) if span_token_sets else set()`.
3. In `projects/01-rag-agent/src/rag_agent/agent.py` (`SYSTEM_PROMPT` Rule 5, lines 41–45):
   - Update Rule 5 to explicitly bound searches on absent topics:
     `"5. Do at most 2–3 search_documents calls per question. If the returned passages do not contain the specific subject, entity, event, or fact asked about, the topic is absent from the corpus: immediately stop calling tools, state in summary that no relevant evidence was found, set confidence below 0.3, and leave citations AND claims EMPTY — never keep reformulating searches or cite passages you judge irrelevant just to satisfy the schema. An honest refusal cites nothing."`
4. Add unit tests:
   - In `tests/test_verify.py`: test that a verbatim span containing `"in September, 2006, killing 154 people."` (with a comma right after `"September"` and `"2006"`) passes `check_claim_spans` with `[]`.
   - In `tests/test_heldout.py`: test that `_judge_context` passes the full `chunk.text` (not just the 240-char `c.excerpt`) of both `evidence` and `output.citations` to the rubric judge.
5. Run `uv run pytest --cov`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy .` from `projects/01-rag-agent` to verify all tests pass locally before any hosted call.

### Step 2: `dev_v1` End-to-End Gate (20 Questions, `kimi-for-coding`)

1. Write `projects/01-rag-agent/scripts/run_e2e_eval.py`:
   - Can run `--split dev_v1` (loads the 20 questions at indices `data/dev_v1.sha256.json["ids"]` from `src/rag_agent/eval_questions.json`, builds the production `S3` retriever from `data/index/chunks_200`, opens a `Checkpoint` under `reports/runs/dev_v1-<sha12>/`, runs `run_rag_eval`, and writes `reports/e2e_dev_v1/metrics.json` and `reports/e2e_dev_v1/question_traces.json`).
   - Also supports `--summarize <reports_dir>` (or runs automatically after evaluation) to compute and write `f1_summary.json` inside `<reports_dir>` with the exact roadmap metrics:
     - For answerable questions (`expected_behavior == "answer"`):
       - True Positive (`TP`): answered (`not abstained`), `verdict == "correct"`, and `cited_relevant == True`.
       - False Negative (`FN`): answerable question that was not `TP` (either `empty-answer` false abstention, `unsupported-claim`, `retrieval-miss`, `budget-terminated`, or `cited_relevant == False`).
     - For unanswerable questions (`expected_behavior == "abstain"`):
       - True Negative (`TN`): `abstained == True` and `verdict == "correct"`.
       - False Positive (`FP`): unanswerable question where the system answered (`not abstained`) or failed (`budget-terminated` / `format-failure`).
     - Compute:
       - `precision = TP / (TP + FP)`
       - `recall = TP / (TP + FN)`
       - `f1 = 2 * TP / (2 * TP + FP + FN)`
       - `overall_accuracy = (TP + TN) / N` (with Wilson 95% interval)
       - Error breakdown: `unsupported_claim`, `false_abstention` (`empty-answer`), `wrong_abstention` (answered an unanswerable question), `budget_terminated`, `format_failure`, `uncited_relevant`.
2. Run `dev_v1` end-to-end with `LLM_COST_LIMIT_USD=0.60` against the single permitted host (`api.kimi.com`, `kimi-for-coding`):
   ```bash
   cd /Users/alejandro/work/portfolio/projects/01-rag-agent
   set -a && . ../../.env && set +a
   export LLM_COST_LIMIT_USD=0.60
   uv run python scripts/run_e2e_eval.py --split dev_v1
   ```
3. Log the `dev_v1` E2E result and spend in `reports/experiment_log.json`.
4. **Gate check:** Verify `dev_v1` `f1 >= 0.85` and `budget_terminated == 0`. If `f1 < 0.85` or `budget_terminated > 0`, stop and report the failure traces before touching `final_v3`.

### Step 3: `final_v3` Checkpointed 120-Question End-to-End Evaluation

1. Once `dev_v1` clears Step 2, run the 120-question `data/golden_final_v3.json` evaluation via the official CLI (which uses `_heldout_checkpoint` under `reports/runs/final_v3-<sha12>/`):
   ```bash
   cd /Users/alejandro/work/portfolio/projects/01-rag-agent
   set -a && . ../../.env && set +a
   export LLM_COST_LIMIT_USD=2.50
   uv run python -m rag_agent.cli evaluate --heldout \
     --heldout-file data/golden_final_v3.json \
     --reports-dir reports/final_v3_e2e
   ```
   *(Note: if the run hits the `$2.50` soft stop near the end of the 120 questions, inspect the checkpoint count in `reports/runs/final_v3-*/rows.jsonl`; if total cumulative spend across Step 1 `$0.1994` + Step 2 `dev_v1` + Step 3 can finish within the `$3.00` hard cap, resume with the remaining cap up to `$2.60` for this process so all 120 questions complete cleanly.)*
2. Run `uv run python scripts/run_e2e_eval.py --summarize reports/final_v3_e2e` to write `reports/final_v3_e2e/f1_summary.json` and append the `final_v3` row to `reports/experiment_log.json`.

### Step 4: Gates & Close-out

```bash
cd /Users/alejandro/work/portfolio/projects/01-rag-agent
uv run pytest --cov
uv run ruff check . && uv run ruff format --check . && uv run mypy .
cd /Users/alejandro/work/portfolio
uv run python scripts/check_docs.py
```

Write `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md` with:
- Step 1 bug fixes and unit test results;
- Step 2 `dev_v1` (20 questions) E2E metrics (`F1`, `precision`, `recall`, `overall_accuracy`, error counts, spend);
- Step 3 `final_v3` (120 questions) E2E metrics (`F1`, `precision`, `recall`, `overall_accuracy` with Wilson 95% CI, faithfulness, taxonomy counts, per-slice breakdown, spend, and request hosts);
- Verbatim gate outputs.

## Stop conditions

- Any hosted request to a host other than the named Kimi API host (`api.kimi.com`).
- Cumulative hosted spend (Step 1 `$0.1994` + Step 2 `dev_v1` + Step 3 `final_v3`) reaching `$3.00`.
- `dev_v1` E2E gate failing (`f1 < 0.85` or `budget_terminated > 0`).
- Coverage dropping below `78.45%`.

## Revision 1 (designer, 2026-11-23): deterministic tool-budget stop, multi-hop synthesis guard, and `--retry-failed` gate re-check

Step 2 achieved `F1 = 0.9032` with `unsupported_claim = 0` on `dev_v1`, but stopped at the gate due to 1 `budget-terminated` unanswerable row (`bad9ea434b83cd45`) and 2 `multi_hop` `empty-answer` rows (`2d24a987fc1c503c`, `86c9e039a2e81e2d`, both of which scored `faithfulness = 0.9` with `claim_states = None`). Apply these 4 binding fixes, re-verify the 3 failed `dev_v1` rows via `--retry-failed`, and proceed directly to Step 3 (`final_v3`):

1. **Deterministic in-tool soft budget ceiling (`src/rag_agent/agent.py`):**
   - In `build_agent(config: RAGConfig, model: Model | None = None)`, compute:
     `soft_req_limit = max(3, config.agent_request_limit - 3)` (`9` at default `12`) and
     `soft_tool_limit = max(4, config.agent_tool_calls_limit - 4)` (`12` at default `16`).
   - At the start of `search_documents(ctx, query, top_k=5)`:
     if `ctx.usage.requests >= soft_req_limit or ctx.usage.tool_calls >= soft_tool_limit`, return `[]`.
   - At the start of `read_excerpt(ctx, citation_id)`:
     if `ctx.usage.requests >= soft_req_limit or ctx.usage.tool_calls >= soft_tool_limit`, return `"TOOL BUDGET REACHED: Do not call any more tools. Emit your final AnalysisResult immediately using only the passages already read, or abstain (confidence < 0.3, citations=[], claims=[]) if the requested fact is not in those passages."`
   - Add a unit test in `tests/test_agent.py` verifying that once `ctx.usage.requests >= soft_req_limit`, `search_documents` returns `[]` and `read_excerpt` returns the `"TOOL BUDGET REACHED"` notice without raising `UsageLimitExceeded`.

2. **Multi-hop synthesis rule & structured-claim verification guard (`src/rag_agent/agent.py`, `src/rag_agent/verify.py`):**
   - In `src/rag_agent/agent.py` `SYSTEM_PROMPT` Rule 10, replace Rule 10 with:
     ```text
     10. Multi-hop and comparison questions: when a question asks how two topics
         relate or compares two topics (e.g. "How does A relate to B?", "Compare A
         with B"), the corpus covers A and B in separate articles that may not
         mention each other. Do NOT abstain when each topic is present in the
         retrieved passages: state the supported facts for A from A's passage(s)
         and for B from B's passage(s), cite every article used with at least one
         verbatim span per leg, and set `confidence >= 0.7`. Never include refusal
         phrases ("no evidence", "no information", "no relevant", "not found",
         "no passage", "cannot answer") inside a substantive answer.
     ```
   - In `src/rag_agent/verify.py` (`_verify`, line 559), change:
     `if is_abstention(result.summary, result.confidence):`
     to:
     `if (not result.claims or result.confidence < 0.3) and is_abstention(result.summary, result.confidence):`
     so a substantive answer with populated `result.claims` and `confidence >= 0.3` runs through `_verify_structured` (which rebuilds `result.summary` strictly from surviving span-backed claims) instead of skipping verification when a caveat substring matches `ABSTENTION_MARKERS`.

3. **Targeted `--retry-failed` resume and `wrong_abstention` accounting (`scripts/run_e2e_eval.py`):**
   - In `summarize_rows` (`scripts/run_e2e_eval.py` line 108), only increment `errors["wrong_abstention"]` on unanswerable rows when `not abstained and verdict not in ("budget-terminated", "format-failure")`.
   - Add `--retry-failed` flag to `scripts/run_e2e_eval.py`: when passed for `--split dev_v1`, before calling `Checkpoint.open(...)`, filter the existing `reports/runs/<run_id>/rows.jsonl` in place to keep only rows where `row["trace"].get("verdict") == "correct"`, and rewrite `reports/runs/<run_id>/manifest.json` with the current `manifest` fields (preserving `cumulative_spend_usd`) so `Checkpoint.open` resumes cleanly from the 17 passing rows ($0) and re-runs only the 3 failed rows (~$0.05).

4. **Execution sequence (Steps 2b → 3 → 4):**
   - Run `uv run pytest --cov`, `ruff`, and `mypy` from `projects/01-rag-agent`.
   - Re-run the 3 failed `dev_v1` rows:
     ```bash
     cd /Users/alejandro/work/portfolio/projects/01-rag-agent
     set -a && . ../../.env && set +a
     export HF_HUB_OFFLINE=1
     export LLM_COST_LIMIT_USD=0.60
     uv run python scripts/run_e2e_eval.py --split dev_v1 --retry-failed
     ```
   - Confirm `dev_v1` clears `f1 >= 0.85` and `budget_terminated == 0`.
   - Immediately run Step 3 (`final_v3`, 120 questions) with `HF_HUB_OFFLINE=1` and the remaining budget cap (`LLM_COST_LIMIT_USD=2.40` process cap so total Step 1 `$0.1994` + Step 2 `~$0.39` + Step 3 stays `<= $3.00`):
     ```bash
     export HF_HUB_OFFLINE=1
     export LLM_COST_LIMIT_USD=2.40
     uv run python -m rag_agent.cli evaluate --heldout \
       --heldout-file data/golden_final_v3.json \
       --reports-dir reports/final_v3_e2e
     uv run python scripts/run_e2e_eval.py --summarize reports/final_v3_e2e
     ```
   - Run all Step 4 gates and update `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md` with the final `dev_v1` and `final_v3` results. Do not commit.
