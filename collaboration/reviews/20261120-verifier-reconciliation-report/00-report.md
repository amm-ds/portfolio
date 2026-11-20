# Verifier reconciliation report (local judge gap)

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-verifier-reconciliation/03-implementation-handoff.md`
(approved: offline reconciliation check only, $0 hosted)
Branch: `verifier-reconciliation-2026-11-20` from `verifier-cascade-2026-11-20`
(head `113032e`). No merge, no deploy. No existing report, cache, rule, fold,
or copy file was edited; the rubric cache was read-only.

## Verdict

**The committed 0.4433 does NOT reproduce.** The entailment prompt run through
the cascade code path gives FA **2/194 = 0.0103** (tolerance was ±1 claim
around 86/194). Per the pre-registered decision rule: *the committed 0.4433
or the cache path is wrong — the discrepancy is reported and this stops; the
cascade result is unchanged.* **The cascade report's "expected from the
prompt change" claim is therefore NOT confirmed**: the rubric-vs-committed
gap is not explained by the prompt difference alone.

## Commits and push

- `b67989d` — `feat(01): reconciliation harness and tests`
- `561ad93` — `feat(01): reconciliation - entailment-prompt verdicts through the cascade code path`
- `469b875` — `feat(01): reconciliation - comparison and decision branch`
- `a4ff9f0` — `fix(01): reconciliation test pins consistency, not the outcome`
- Pushed with upstream ✓

## Step 1 — prompts and code paths (verbatim, hashed)

**Rubric prompt** (used by the cascade cache):
- File: `projects/01-rag-agent/src/rag_agent/judge.py` — `RUBRIC_SYSTEM_PROMPT`
  (constant) + user prompt `Question: {question}\n\nContext:\n{context}\n\nAnswer:\n{answer}`
  from `LLMRubricJudge.judge`.
- Verbatim system prompt:

```
You are a strict grader for retrieval-grounded answers.

Score 1.0 only if the answer is fully supported by the provided context AND
addresses the question. Score near 0.0 if the answer contradicts the context,
invents facts not present in it, or fails to address the question. Use
intermediate scores for partial support or partial relevance. Always give a
one-sentence reason.
```

- sha256: `dba00ba99d6d156133f46b5b810ff631d2ca3d5289348c2bde91367559d1a318`
  (identical to the hash recorded in the committed rubric cache header ✓)

**Entailment prompt** (produced the committed 0.4433):
- File: `projects/01-rag-agent/scripts/calibrate_judge.py` — `CLAIM_PROMPT`
  (module constant) + inline system prompt in `evaluate()`'s local judge
  Agent + `ClaimVerdict{supported: bool, reason}`.
- Verbatim claim prompt:

```
You are a strict entailment judge for retrieval-grounded answers.

Question: {question}

Evidence:
{evidence}

Claim: {claim}

Decide whether the evidence fully supports the claim. Any fact, number, date,
or inference not present in the evidence makes the claim unsupported.
```

- Verbatim system prompt: `You check whether claims are entailed by retrieved evidence. You are strict: unsupported means the evidence does not state it. You never use outside knowledge.` (asserted verbatim against the calibrate_judge source, fragments and all).
- sha256s: claim prompt `18d47b1702bb6f1c578bad4b46a6c18fcb32c45c6caf92f75728386a23c1a5ed`,
  system prompt `16ee433a3c246f56aa2ce8467c9d4407e7b5e608a60e41df5b8345c39f0445d4`.

**Traceability**: `reports/judge_calibration/results.json` schema matches
`calibrate_judge.py`'s gates output exactly (model qwen2.5:3b, n_claims 194,
repeat_runs 2, FA 0.4433, FR 0.0103); the judge calibration report describes
the same path. The committed record, however, carries **no model digest, no
commit, no dataset sha256, and no per-claim verdicts**.

## Step 2 — entailment run through the cache path

Forced-local `qwen2.5:3b` (digest confirmed before the run:
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`),
`NativeOutput(ClaimVerdict)`, `Settings(llm_base_url=None, llm_api_key=None)`,
same `model_settings_for_provider()` and `retries={"output": 2}` as the
cascade cache. 194/194 claims, **0 unparseable**, 286.28 s, every request to
`localhost:11434`, $0 hosted.

## Step 3 — both prompts on the same 194 claims

| prompt | FA all claims (Wilson 95%) | FA strict /97 (Wilson 95%) | FR /97 (Wilson 95%) |
|---|---|---|---|
| rubric (judge.py) | 23/194 = 0.1186 [0.0803, 0.1716] | 23 = 0.2371 [0.1635, 0.3307] | 12 = 0.1237 [0.0722, 0.2039] |
| entailment (calibrate_judge.py) | 2/194 = 0.0103 [0.0028, 0.0368] | 2 = 0.0206 [0.0057, 0.0721] | 83 = 0.8557 [0.7722, 0.912] |

- Prompt agreement: **100/194 = 0.5155**.
- 2×2 (rubric rows × entailment cols) against gold:
  - supported: accept/accept 14, accept/reject 71, reject/accept 0, reject/reject 12
  - unsupported: accept/accept 1, accept/reject 22, reject/accept 1, reject/reject 73
- The entailment run accepted only 16/194 claims; its rejected-supported
  reasons are coherent and prompt-faithful (hyper-literal strictness, e.g.
  "the evidence does not explicitly list these components"), so the current
  cache path behaves sanely under both prompts.

**Reconciliation**: entailment FA all claims = 2/194 vs committed 86/194 —
not within ±1 claim. **Reproduced: false.** Decision branch: *the committed
0.4433 or the cache path is wrong; discrepancy reported; cascade result
unchanged.*

## What this means

- The cascade's own result (no qualifying band, rubric cache) is untouched
  and stands on its own artifacts.
- The cascade report's reconciliation caveat said the rubric-vs-committed
  gap was "expected" from the prompt change. **Not confirmed**: with the
  entailment prompt on the same code path, the gap to 0.4433 is 84 claims —
  far beyond prompt-style variation given the same model name.
- The two extreme operating points (R7 record: ~94% acceptance; today:
  ~8% acceptance, same nominal config) plus the missing digest/commit in the
  R7 record point at an unverifiable historical run or environment drift,
  not at a demonstrated bug in the current cache path.

## Gates (actual output)

- `uv run pytest -q projects/01-rag-agent` → **204 passed, 0 failed**; exit 1
  solely from the pre-existing libs coverage gate (`Required test coverage of
  80.0 not reached. Total coverage: 78.19%`) — reported separately per the
  handoff; threshold untouched.
- `uv run ruff check projects/01-rag-agent` → `All checks passed!`
- `uv run ruff format --check` on the new files → `2 files already formatted`
- `uv run mypy projects/01-rag-agent/src projects/01-rag-agent/scripts` →
  `Success: no issues found in 35 source files`
- `uv run python scripts/check_headline_numbers.py` → `11 claims checked,
  0 finding(s)` / `OK`
- `uv run python scripts/check_docs.py` → `check-docs: OK`

## Zero-hosted-calls statement

Zero hosted calls, $0. All model traffic in this pass went to
`http://localhost:11434` (Ollama), forced-local by construction
(`Settings(llm_base_url=None, llm_api_key=None)`; env kwargs beat the `.env`
file). The digest was confirmed before the run.

## Open questions

1. **Model blob drift (prime suspect)**: the R7 record has no digest. If the
   local `qwen2.5:3b` blob was re-pulled between R7 and today, both extreme
   behaviors are explained without any code bug. Unverifiable retroactively.
2. **Runtime drift**: ollama server version and pydantic-ai `NativeOutput`
   grammar handling may have changed between R7 and today (uv.lock pins the
   Python side; the model server is uncontrolled).
3. **R7 run anomaly**: rates came from pass 0 of 2 with no per-claim record;
   the arithmetic coincidence 43/97 = 86/194 also means the committed
   number's denominator convention was ambiguous in the record.
4. **Label-set evolution**: `claims.jsonl` has no sha in the R7 record; its
   current sha (`675ac742…`) cannot be compared to what R7 scored.

Recommended next step (owner decision, not executed): re-run
`calibrate_judge.py` as-is (its own code path, repeat 2) to see whether the
entailment prompt reproduces 0.4433 under its ORIGINAL script today; that
separates "script/code-path difference" from "environment drift" without
touching any artifact from this handoff.
