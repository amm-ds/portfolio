# Architecture proposal: Full-chunk judge context, punctuation-safe span verification, and checkpointed `dev_v1` → `final_v3` E2E execution

Date: 2026-11-23
Designer: Claude Code
Source brief: `collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/01-design-brief.md`

## 1. Full-chunk judge context in `src/rag_agent/evaluate.py`

In `run_rag_eval` (`src/rag_agent/evaluate.py` around line 740), replace:

```python
context = "\n".join(c.excerpt for c in evidence)
```

with a helper `_judge_context(evidence: list[Citation], cited: list[Citation], retriever: Retriever) -> str`:

```python
def _judge_context(evidence: list[Citation], cited: list[Citation], retriever: Retriever) -> str:
    """Full chunk texts for the rubric judge: retrieved top-k union agent-cited chunks.

    Falls back to ``c.excerpt`` only when ``retriever.get_chunk(c.chunk_id)`` is
    None (e.g. minimal mock retrievers in unit tests).
    """
    seen: set[str] = set()
    parts: list[str] = []
    for c in [*evidence, *cited]:
        if c.chunk_id in seen:
            continue
        seen.add(c.chunk_id)
        chunk = retriever.get_chunk(c.chunk_id)
        parts.append(chunk.text if chunk is not None else c.excerpt)
    return "\n\n".join(parts)
```

Also update `retrieved_relevant` / `cited_relevant` accounting: if the agent found and cited a relevant article via `search_documents` (`cited_relevant == True`), `retrieved_relevant` is also `True` (since `search_documents` is the retriever tool!).

## 2. Punctuation-safe span tokenization in `src/rag_agent/verify.py`

In `check_claim_spans` (`src/rag_agent/verify.py` lines 257–276), precompute alphanumeric word sets for each normalized span using `_WORD_RE = re.compile(r"[a-z0-9]+")` (identical to `gate.content_words`):

```python
span_token_sets = [set(re.findall(r"[a-z0-9]+", s)) for s in span_texts]
```

Use `span_token_sets` instead of `s.split()` in:
- Entity co-occurrence check for numbers: `any(w in span_tokens for w in others)`
- Month / temporal qualifier check: `any(token in span_tokens for span_tokens in span_token_sets)`
- Span negation union: `span_words = set().union(*span_token_sets) if span_token_sets else set()`

## 3. Bounded unanswerable search rule in `src/rag_agent/agent.py`

In `SYSTEM_PROMPT` Rule 5 (`src/rag_agent/agent.py` lines 41–45):

```text
5. Do at most 2–3 search_documents calls per question. If the returned passages
   do not contain the specific subject, entity, event, or fact asked about,
   the topic is absent from the corpus: immediately stop calling tools, state
   in `summary` that no relevant evidence was found, set `confidence` below 0.3,
   and leave `citations` AND `claims` EMPTY — never keep reformulating searches
   or cite passages you judge irrelevant just to satisfy the schema.
```

## 4. Two-stage End-to-End Execution (`dev_v1` gate → `final_v3` one-time pass)

1. **`dev_v1` End-to-End Gate (20 questions from `data/dev_v1.sha256.json`):**
   - Run `run_rag_eval` on the 20 `dev_v1` questions against `kimi-for-coding` (`api.kimi.com`), writing `reports/e2e_dev_v1/metrics.json` and `reports/e2e_dev_v1/question_traces.json`.
   - Compute the roadmap metrics:
     - Per-question F1 (positive class = fully correct answer on answerable question: answered, `verdict == "correct"`, `cited_relevant == True`; negative class = correct abstention on unanswerable question).
     - Error counts: `unsupported-claim`, `empty-answer` (false abstention), wrong abstention (answering an unanswerable question), `budget-terminated`, `format-failure`.
   - **Promotion Gate to `final_v3`:** `dev_v1` per-question F1 $\ge 0.85$ and `budget-terminated == 0`.
2. **`final_v3` One-Time Checkpointed Pass (120 questions from `data/golden_final_v3.json`):**
   - Run `uv run python -m rag_agent.cli evaluate --heldout --heldout-file data/golden_final_v3.json --reports-dir reports/final_v3_e2e` with `LLM_COST_LIMIT_USD=2.50` (soft stop; hard cap `$2.80` so cumulative Step 1 `$0.1994` + Phase E stays $\le \$3.00$).
   - If the soft stop `$2.50` is reached near the end of the 120 questions, resume seamlessly from the per-question checkpoint (`reports/runs/final_v3-<sha12>/rows.jsonl`) with `LLM_COST_LIMIT_USD=2.80` to complete all 120 questions without losing a single completed row.
