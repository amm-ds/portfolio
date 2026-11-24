# Review response: Phase E (Steps 1–2) — Pipeline Bug Fixes & `dev_v1` E2E Gate

Date: 2026-11-23
Reviewer: Claude Code
Implementation: working tree on `phase0-infra-2026-11-22`, reported in `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md`
Status: changes requested (Revision 1 — deterministic tool-budget stop + multi-hop synthesis guard, then `--retry-failed` on the 3 failed `dev_v1` rows and proceed to Step 3 `final_v3`)

## Verdict

Step 1 and Step 2 validated the core hypothesis:

- Fixing `_judge_context` to pass full `chunk.text` (`[*evidence, *output.citations]`) reduced **`unsupported_claim` to `0` (`0/20`)** on `dev_v1` (down from 25–30% in every prior evaluation) and achieved **`F1 = 0.9032`** (`12/12` `single_hop` correct, `2/4` `multi_hop` correct, `3/4` `unanswerable` correct).
- Kimi properly honored the Step 2 stop condition (`budget_terminated == 1` on `"What is the capital of Australia?"`) and halted before touching `final_v3`.

Forensic inspection of the 3 non-correct `dev_v1` rows (`reports/runs/dev_v1-ed9013955903/rows.jsonl`) shows all 3 are deterministically fixable before running Step 3 (`final_v3`):

1. **`bad9ea434b83cd45` (`"What is the capital of Australia?"`, `unanswerable` → `budget-terminated` at `request_limit=12`):**
   Because `"Australia"` appears in the corpus (`"Biofuel in Australia"`), the model kept calling `search_documents` / `read_excerpt` until `pydantic-ai` raised `UsageLimitExceeded("request_limit of 12")`. A prompt instruction alone is probabilistic; adding a **deterministic in-tool soft ceiling** inside `search_documents` and `read_excerpt` (`ctx.usage.requests >= max(3, config.agent_request_limit - 3)` or `ctx.usage.tool_calls >= max(4, config.agent_tool_calls_limit - 4)`) stops tool calls 3 requests before the hard rail and tells the model to emit its final `AnalysisResult` immediately.
2. **`2d24a987fc1c503c` and `86c9e039a2e81e2d` (the 2 `multi_hop` `empty-answer` rows — both scored `faithfulness = 0.9` with `claim_states = None`):**
   On both multi-hop questions (`"How does climate change adaptation relate to greenhouse gas inventories..."` and `"Compare space-based solar power with wind power in Europe..."`), the two topics live in separate articles that do not mention each other. Because Rule 5 told the model to abstain if no passage contained the specific relationship asked about (and because `is_abstention` in `verify.py:559` skipped verification whenever `summary` contained a caveat substring like `"no evidence"` / `"no passage"` even when `result.claims` and `result.citations` were populated with `confidence >= 0.3`), both `0.9`-faithfulness answers were turned into `empty-answer`.

## Required changes (Revision 1)

| Severity | Finding | Evidence | Required resolution |
|---|---|---|---|
| blocker | Probabilistic prompt rule allowed 1 unanswerable row (`bad9ea434b83cd45`) to hit `request_limit=12` (`UsageLimitExceeded`) | `reports/e2e_dev_v1/question_traces.json` line 259 | In `src/rag_agent/agent.py` (`build_agent`), enforce a deterministic soft tool ceiling in `search_documents` and `read_excerpt` when `ctx.usage.requests >= max(3, config.agent_request_limit - 3)` or `ctx.usage.tool_calls >= max(4, config.agent_tool_calls_limit - 4)`: `search_documents` returns `[]` and `read_excerpt` returns `"TOOL BUDGET REACHED: Stop calling tools immediately and return your final AnalysisResult now using the passages already retrieved (or abstain with confidence < 0.3, citations=[], claims=[] if the answer is not in those passages)."` |
| major | Multi-hop comparison/relationship questions over separate articles false-abstain or trigger `is_abstention` via caveat substrings (`2d24a987fc1c503c`, `86c9e039a2e81e2d`, both `faithfulness=0.9`, `claim_states=None`) | `reports/e2e_dev_v1/question_traces.json` lines 26–45, 183–202; `src/rag_agent/verify.py:559` | 1. In `src/rag_agent/agent.py` `SYSTEM_PROMPT` Rule 10, instruct the agent not to abstain when two multi-hop topics are covered in separate articles that don't cross-reference each other (state supported facts for each leg with citations/verbatim spans and `confidence >= 0.7`, and never include refusal phrases like `"no evidence"` / `"no information"` / `"not found"` / `"no passage"` inside a substantive answer).<br>2. In `src/rag_agent/verify.py` line 559, only skip verification when `(not result.claims or result.confidence < 0.3) and is_abstention(result.summary, result.confidence)`. |
| minor | `summarize_rows` in `scripts/run_e2e_eval.py` counts `budget-terminated` unanswerable rows as `wrong_abstention` (`fp`), and re-gating all 20 `dev_v1` rows from scratch would waste $0.30 | `scripts/run_e2e_eval.py:108-113` | 1. Only increment `errors["wrong_abstention"]` when `not abstained and verdict not in ("budget-terminated", "format-failure")`.<br>2. Add `--retry-failed` to `scripts/run_e2e_eval.py` to prune non-`correct` rows from `reports/runs/dev_v1-*/rows.jsonl` and refresh `manifest.json` identity so the 17 passing rows are reused for $0 and only the 3 failed rows are re-run (~$0.05). |

## Verification checked

- [x] Step 1 bug fixes and unit tests verified (`183 passed`, `ruff`/`mypy` clean)
- [x] Step 2 stop condition respected (`final_v3` untouched)
- [x] `HF_HUB_OFFLINE=1` added to prevent HuggingFace status pings

## Next step

Commit Step 1–2 progress and Revision 1 handoff, then Kimi applies Revision 1, runs `uv run python scripts/run_e2e_eval.py --split dev_v1 --retry-failed`, confirms `f1 >= 0.85` and `budget_terminated == 0`, and proceeds immediately to Step 3 (`final_v3` 120-question evaluation with `HF_HUB_OFFLINE=1` and the remaining `$2.42` cap).
